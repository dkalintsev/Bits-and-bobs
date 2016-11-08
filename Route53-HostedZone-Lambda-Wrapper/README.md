# AWS::Route53::HostedZone Lambda wrapper

By default, CloudFormation resource AWS::Route53::HostedZone will not delete when the stack is deleted if the zone has been modified by means other than the template itself. For example, you may come across this problem if your autoscaled instances register their own IP addresses in a Route53 Hosted Zone through API or AWS CLI. [AWS' recommendation](https://forums.aws.amazon.com/thread.jspa?threadID=148764) is to handle such situations by issuing stack updates, but I think it's a tad painful to do it that way.

As a work-around, I wrote a Lambda function that you can call as a Custom CloudFormation Resource to create a Hosted Zone. When you delete your stack, the "DELETE" handler in this function will iterate over the contents of the Hosted Zone, and delete all records before deleting the zone itself.

Please see the `HostedZone-wrapper.template` for a usage example. Pay attention to the IAM permissions your Lambda function will need.

Lambda-backed Custom Resource expects the following parameters, similar to AWS::Route53::HostedZone but with some differences:

- HostedZoneConfig: In additon to 'Comment', you can specify an additonal parameter 'PrivateZone': True|False to set HostedZone type.
- HostedZoneTags: same as Route53::HostedZone.
- Name: same as Route53::HostedZone.
- VPC: Supports only one VPC; key/value list of: 'VPCRegion' and 'VPCId'.

Through the use of Fn::GetAtt, the resulting custom resource can return the following:

- HostedZoneId - same as Route53::HostedZone, and
- NameServers[] - an array of 4 strings with the Route53 name servers for this HostedZone, when you create a public Hosted Zone.
