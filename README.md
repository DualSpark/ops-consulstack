# consulstack
[Consul.io ](https://consul.io/) server cluster replicated across availability zones in a specified AWS::Region using [troposphere](https://github.com/cloudtools/troposphere)-generated Cloudformation templates.

## Getting Started

### Using a [Python virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/) to isolate dependencies:

```bash
git clone git@github.com:dualspark/ops-consulstack
cd ops-consulstack
pip install virtualenvwrapper
mkvirtualenv consulstack
python setup.py develop
```

When working on this project in the future, use `workon consulstack` to activate the configured environment and `deactivate` when you're finished.

### Configuring AWS authentication

If you have the [AWS CLI](http://aws.amazon.com/cli/) installed and  configured, there's nothing else to do.

If you do not have the AWS CLI installed, follow the instructions on the [AWS CLI](http://aws.amazon.com/cli/) page.  Then run `aws configure` to set up your credentials.

You can also manually create the following two files:  

**~/.aws/credentials**
```
[default]
aws_access_key_id = ACCESS_KEY
aws_secret_access_key = SECRET_KEY
```

**~/.aws/config**
```
[default]
output = json
region = us-west-2
```

### Creating an EC2 key pair for SSH

You need to [generate an EC2 Key Pair](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html) to use to SSH into instances. The name of this key is arbitrary, but it is needed to configure the network deployment process.  You can reuse an existing key pair if desired.

## Using ops-consulstack

Run the consulstack.py file:

```bash
./src/consulstack.py create
```

This will gather information from your AWS account to know what regions and availability zones are available.  It will then create a default config.json file and a Cloudformation template named environmentbase.template.

### Customizing config.json

 The following are the minimal set of items that are necessary to validate:

* within the 'template' section:
  * Set the value of ec2_key_default to the key pair name mentioned above.
  * Set the value of remote_access_cidr to a CIDR range that you want to be able to access the bastion host from. This is a single CIDR range (for now) and could be the network egress CIDR for a corporate office, etc.
* within the 'network' section:
  * Set the values of the network size and CIDR base to your liking/needs. Note that this process will create a public and private subnet in each of the AWS Availability Zones configured (in order, up to 3).

### Running ops-consulstack

```bash
./src/consulstack.py create
./src/consulstack.py deploy
```

## What's created

By using [cloudformation-environmentbase](https://github.com/DualSpark/cloudformation-environmentbase), a VPC is included in the generated Cloudformation template.  Check that project's [Readme](https://github.com/DualSpark/cloudformation-environmentbase/blob/master/README.md) to see more information about the VPC.

A child Cloudformation stack is created for the Consul stack.  This allows more flexibility for updating the stack or removing it, but leaving the VPC intact.  This child stack is stored in the S3 bucket referenced in config.json.  The parent stack refers to the stack by its S3 URL.  Snippet showing the reference:

```
"ConsulStack":{
"Type":"AWS::CloudFormation::Stack",
"Properties":{
"TemplateURL":"https://BUCKETNAME.s3.amazonaws.com/devtools/cloudformation/ConsulStack.1438189565.template"
```

### Sample Agents

Included in this repository I have created an agent node in each AZ. This has one web service running with health checks.

### Atlas Integration

If you choose to Atlas integration. 
```
https://atlas.hashicorp.com/{atlas-username}/environments/{atlas-envname}
```

