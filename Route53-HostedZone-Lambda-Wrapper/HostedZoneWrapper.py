#
# Lambda function for use in CF templates instead of AWS::Route53::HostedZone
# Compared to stock function, this is meant to:
# 1) Delete the zone with any records added outside the CF path (CLI/API)
# 2) Return the NS records for the DelegationSet that you can use elsewhere,
#    when you create Public Hosted Zone.
#
# If you strip comments and change spaces to tabs, this function fits into
# 4096 byte in-line code limit. See sed command at the bottom to make inlive version.
#
# State of this as of now:
# - Haven't tested with large zones (more than a handful of records)
# - There's no "UPDATE" method implemented
#
import json
import cfnresponse
import boto3
import random
import string
import sys
#
def handler(event, context):
    # This function handles two RequestTypes: CREATE and DELETE
    if event['RequestType'] == 'Delete':
        client = boto3.client('route53')
        # CREATE handler below puts the new Zone ID into PhysicalResourceId
        hostedZoneId = event['PhysicalResourceId']
        zones = client.list_hosted_zones()
        # PhysicalResourceId has hostedZoneId as value only, no /hostedzone/
        myZone = filter(lambda find_rec: find_rec['Id'] == '/hostedzone/'+hostedZoneId, zones['HostedZones'])
        # We expect only one match. Otherwise we just bail.
        if len(myZone) == 1:
            try:
                # At this point, we don't handle responses with more than 100 records,
                # where response['IsTruncated'] == True
                print 'Listing resource record sets..'
                response = client.list_resource_record_sets (
                    HostedZoneId = hostedZoneId
                )
                if len(response['ResourceRecordSets']) > 2:
                    # Empty zone will always have at least 2 records: SOA and NS
                    # If there are more than 2, we have work to do
                    print 'Iterating over records to delete..'
                    for record in response['ResourceRecordSets']:
                        if record['Type'] != 'SOA' and record['Type'] != 'NS':
                            print 'Deleting record: ', record
                            result = client.change_resource_record_sets (
                                HostedZoneId = hostedZoneId,
                                ChangeBatch = {
                                    "Changes": [
                                        {
                                            "Action": "DELETE",
                                            "ResourceRecordSet": record
                                        }
                                    ]
                                }
                            )
                print 'Deleting the zone itself..'
                response = client.delete_hosted_zone (
                    Id = hostedZoneId
                )
                print 'Deleted the zone successfully.'
                responseData = {}
                responseData['HostedZoneId'] = hostedZoneId
                cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, event['PhysicalResourceId'])
            except Exception as err:
                print 'Error encountered: ', err, sys.exc_info()[0]
                responseData = {}
                cfnresponse.send(event, context, cfnresponse.FAILED, responseData, event['PhysicalResourceId'])
        else:
            print 'Zone ID lookup did not return exactly one result, bailing.'
            responseData = {}
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, event['PhysicalResourceId'])
#
    elif event['RequestType'] == 'Create':
        client = boto3.client('route53')
        kwargs = {}
        z_name=event['ResourceProperties']['Name']
        if z_name[-1] != '.':
            z_name = z_name + '.'
        kwargs['Name'] = z_name
        kwargs['CallerReference'] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        # If HostedZoneConfig and/or Region/VPC are specified, put them into request
        hzconf = event['ResourceProperties'].get('HostedZoneConfig', None)
        region = event['ResourceProperties'].get('Region', None)
        vpc = event['ResourceProperties'].get('VPC', None)
        hztags = event['ResourceProperties'].get('HostedZoneTags', None)
        if vpc:
            kwargs['VPC'] = vpc
        if hzconf:
            hzc1 = {}
            hzc1['Comment'] = hzconf.get('Comment', None)
            pz = hzconf.get('PrivateZone', None)
            if pz:
                # CloudFormation sends Bool variables "true" / "false" as String
                hzc1['PrivateZone'] = json.loads(pz)
            kwargs['HostedZoneConfig'] = hzc1
        try:
            print 'Creating the Hosted Zone..'
            response = client.create_hosted_zone (**kwargs)
            # Id has /hostedzone/ as part of it
            hostedZoneId1 = response['HostedZone']['Id']
            hostedZoneId = str.split(str(hostedZoneId1),'/')[2]
            print 'New Hosted Zone created:', hostedZoneId
            responseData = {}
            responseData['HostedZoneId'] = hostedZoneId
            # There is no DelegationSet returned when we created a Private Hosted Zone.
            ds = response.get('DelegationSet', None)
            if ds:
                # Return Name Servers if we have DelegationSet
                responseData['NameServers'] = ds['NameServers']
            else:
                # Return "info message" instead of Name Servers if we created a Private Hosted Zone
                responseData['NameServers'] = ['Private zone created', 'No DelegationSet returned', '', '']
            if hztags:
                # create_hosted_zone doesn't set Tags;
                # if HostedZoneTags specified, we need to set tags separately
                print 'HostedZoneTags is supplied; applying tags to the new zone.'
                kwags = {}
                kwags['ResourceType'] = 'hostedzone'
                kwags['ResourceId'] = hostedZoneId
                kwags['AddTags'] = hztags
                response = client.change_tags_for_resource(**kwags)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, hostedZoneId)
        except Exception as err:
            print 'Error encountered: ', err, sys.exc_info()[0]
            responseData = {}
            hostedZoneId = 'XXX'
            responseData['HostedZoneId'] = hostedZoneId
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData, hostedZoneId)
    else:
        print 'RequestType is not Create or Delete; bailing.'
        cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, event['PhysicalResourceId'])
#
# To prep this code for in-line CF (mind the \t in the last sed edit set):
# cat HostedZoneWrapper.py | grep -v '#' | sed -e 's/\"/\\"/g' -e 's/^/\"/g' -e 's/$/\",/g' -e 's/    /	/g'
# (Need to convert spaces to tabs since CF only allows in-line Lambdas smaller than 4096 bytes)