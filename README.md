# consulstack
[Consul.io ](https://consul.io/) server cluster replicated across availability zones in a specified AWS::Region using [troposphere](https://github.com/cloudtools/troposphere)-generated Cloudformation templates.

## Getting Started

### Using a [Python virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/) to isolate dependencies:

```bash
git clone https://github.com/DualSpark/ops-consulstack.git
cd ops-consulstack
pip install virtualenvwrapper
mkvirtualenv consulstack
python setup.py develop
```

When working on this project in the future, use `workon consulstack` to activate the configured environment and `deactivate` when you're finished.
```bash
deactivate
```
Note: This is only available after you run workon consulstack.

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
cd src
python consulstack.py create
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
python consulstack.py create
python consulstack.py deploy
```

## What's created

By using [cloudformation-environmentbase](https://github.com/DualSpark/cloudformation-environmentbase), a VPC is included in the generated Cloudformation template.  Check that project's [Readme](https://github.com/DualSpark/cloudformation-environmentbase/blob/master/README.md) to see more information about the VPC.

A child Cloudformation stack is created for the Consul stack.  This allows more flexibility for updating the stack or removing it, but leaving the VPC intact.  This child stack is stored in the S3 bucket referenced in config.json.  The parent stack refers to the stack by its S3 URL.  Snippet showing the reference:

```
"ConsulStack":{
"Type":"AWS::CloudFormation::Stack",
"Properties":{
"TemplateURL":"https://BUCKETNAME.s3.amazonaws.com/devtools/cloudformation/ConsulStack.{dynamic id}.template"
```

### Sample Agents

Included in this repository I have created an agent node in each AZ. This has one web service running with health checks. Each sample node is running nginx as a standalone web server. The health checks are configured in the templates/ folder.

consul-web.json
```json
{
	"service": 
	{
		"name": "web", 
		"tags": ["web"], 
		"port": 80,
  		"check": 
  			{
  				"script": "curl localhost >/dev/null 2>&1", "interval": "10s"
  			}
	}
}
```
This registers a service named web with the agent. There is a sample mysql config file as well if your ami supports it.


### Access Members

You will need to ssh through your [Bastion host](https://github.com/DualSpark/cloudformation-environmentbase/blob/master/src/environmentbase/patterns/bastion.py) that was created as part of [Cloudformation EnvironmentBase](https://github.com/DualSpark/cloudformation-environmentbase)

```bash
ssh -A -i ~/path-to-ssh/key-you-specified-in-config.pem ubuntu@dns-aname-for-load-balancer
```
After connecting to the Bastion host you can then connect to your consul members.

```bash
ssh -A ubuntu@10.0.64.4
```

now run

```bash
consul members
```
You should a list of all connected nodes across Availability Zones. 





### Atlas Integration

If you choose to Atlas integration. 
You will need to set up an account at [Hashicorp](https://atlas.hashicorp.com/). You can read all about it on the [Consul.io](https://www.consul.io/docs/guides/atlas.html) site. In the config.json file that is created you can add the following 

```json
    "atlas": {
        "atlas-token": "token-that-you-setup-earlier",
        "atlas-username": "{username}/{envname}"
    },
```

After integration, once you deploy the stack you can access your dashboard at:

```
https://atlas.hashicorp.com/{atlas-username}/environments/{atlas-envname}
```
