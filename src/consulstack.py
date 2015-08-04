"""
consulstack

Tool bundle manages generation, deployment, and feedback of cloudformation resources.

Usage:
    consulstack (create|deploy) [--config-file <FILE_LOCATION>] [--debug] [--template-file=<TEMPLATE_FILE>]

Options:
  -h --help                            Show this screen.
  -v --version                         Show version.
  --debug                              Prints parent template to console out.
  --config-file <CONFIG_FILE>          Name of json configuration file. Default value is config.json
  --stack-name <STACK_NAME>            User-definable value for the CloudFormation stack being deployed.
  --template-file=<TEMPLATE_FILE>      Name of template to be either generated or deployed.
"""

from environmentbase.networkbase import NetworkBase
from environmentbase.cli import CLI
from environmentbase.template import Template
from environmentbase import template
from troposphere import ec2, Tags, Ref, iam, GetAtt, Join, FindInMap, Output, \
Select, Base64
from troposphere.ec2 import NetworkInterfaceProperty
import troposphere.iam as iam
import boto.vpc
import boto
import json
from environmentbase import resources
from environmentbase.patterns import bastion
from pprint import pprint


class ConsulTemplate(Template):


    DEFAULT_POLICY = iam.Policy(
        PolicyName='cloudformationRead',
        PolicyDocument={
            "Statement": [{
                  "Effect": "Allow",
                  "Action": [
                      "cloudformation:DescribeStackEvents",
                      "cloudformation:DescribeStackResource",
                      "cloudformation:DescribeStackResources",
                      "cloudformation:DescribeStacks",
                      "cloudformation:ListStacks",
                      "cloudformation:ListStackResources"],
                  "Resource": "*"}]})
    # Load USER_DATA scripts from package
    BOOTSTRAP_SH = resources.get_resource('consul_bootstrap.sh', __name__)

    # When no config.json file exists a new one is created using the 'factory default' file.  This function
    # augments the factory default before it is written to file with the config values required by an ConsulTemplate
    @staticmethod
    def get_factory_defaults():
        return {'consul': {
            'ami_id': 'ubuntu1404LtsAmiId',
        }}

    # When the user request to 'create' a new ELK template the config.json file is read in. This file is checked to
    # ensure all required values are present. Because ELK stack has additional requirements beyond that of
    # EnvironmentBase this function is used to add additional validation checks.
    @staticmethod
    def get_config_schema():
        return {'consul': {
            'ami_id': 'str'
        }}

    

    # Collect all the values we need to assemble our ELK stack
    def __init__(self, env_name, ami_id, boto_config={}):
        super(ConsulTemplate, self).__init__('ConsulStack')
        self.env_name = env_name
        self.ami_id = ami_id
        self.boto_config = boto_config
    # Called after add_child_template() has attached common parameters and some instance attributes:
    # - RegionMap: Region to AMI map, allows template to be deployed in different regions without updating AMI ids
    # - ec2Key: keyname to use for ssh authentication
    # - vpcCidr: IP block claimed by whole VPC
    # - vpcId: resource id of VPC
    # - commonSecurityGroup: sg identifier for common allowed ports (22 in from VPC)
    # - utilityBucket: S3 bucket name used to send logs to
    # - availabilityZone[0-9]: Indexed names of AZs VPC is deployed to
    # - [public|private]Subnet[0-9]: indexed and classified subnet identifiers
    #
    # and some instance attributes referencing the attached parameters:
    # - self.vpc_cidr
    # - self.vpc_id
    # - self.common_security_group
    # - self.utility_bucket
    # - self.subnets: keyed by type and index (e.g. self.subnets['public'][1])
    # - self.azs: List of parameter references
    def build_hook(self):
        self.create_consul_cluster()


    def create_consul_cluster(self):

        #t_config = self.config.get('template')
        consul_security_group = self.create_consul_sg()

        startup_vars = []
        startup_vars.append(Join('=', ['REGION', Ref('AWS::Region')]))
        startup_vars.append(Join('=', ['UI', '/var/consul/ui']))
        startup_vars.append(Join('=', ['DATA', '/var/consul/data']))
        startup_vars.append(Join('=', ['JOIN', '"10.0.16.4"']))
        startup_vars.append(Join('=', ['CONFIG', '/etc/consul']))
        startup_vars.append(Join('=', ['AZCOUNT', len(self.azs)]))

        p_ids = []

        for index in range(len(self.azs)):
            p_ids.append("10.0.%s.4" % ((16 + 16) * (index+1)))

        #Get our server config strings
        p_id_str = ','.join(map(str,p_ids))

        #Grab our consul.conf file to distribute to nodes
        with open('templates/consul.json') as json_file:
            json_data = json.load(json_file)


        for index in range(len(self.azs)):
            name = 'ConsulHost%s' % (index + 1)

            #p_id = '10.0.%s.4' % ((16 + 16) * (index+1))
            json_data['start_join'] = p_ids
            json_data['data_dir'] = '/var/consul/data'
            json_data['ui_dir'] = '/var/consul/ui'
            json_data['datacenter'] = "{0}-{1}".format('us-west-2',name)


            if(index == 0):
                json_data['bootstrap_expect'] = len(self.azs)
                if(json_data.get('start_join')):
                    del json_data['start_join']
            else:
                if(json_data.get('bootstrap_expect')):
                    del json_data['bootstrap_expect']

            pprint(json_data)
            # pprint(boto_config.get('region_name', 'us-west-2'))
            # region = template.tropo_to_string(Ref('AWS::Region'))
            # import pdb; pdb.set_trace()
            #print template.tropo_to_string(self)
            #print template.tropo_to_string(self.subnets['private'][index])
            #print "Configuring {0} with security group {1}".format(name, consul_security_group)
            #print "Configuring {0} with security group {1}".format(name, self.common_security_group)
            consul_host = self.add_resource(ec2.Instance(
                name,
                InstanceType="m1.small",
                KeyName=Ref(self.parameters['ec2Key']),
                ImageId=FindInMap('RegionMap', Ref('AWS::Region'), self.ami_id),
                #SecurityGroups=[Ref(consul_security_group)],
                #AvailabilityZone=Ref(self.azs[index]),
                NetworkInterfaces=[
                    ec2.NetworkInterfaceProperty(
                        Description='ENI for CONSUL hosts',
                        GroupSet=[Ref(consul_security_group)],
                        SubnetId=self.subnets['private'][index],
                        PrivateIpAddress = p_ids[index],
                        DeviceIndex=0,
                        DeleteOnTermination=True
                    )
                ],
                UserData=Base64(Join('', [
                    '#!/bin/bash\n\n',
                    #'sudo apt-get update\n',
                    #'sudo apt-get -y install python-setuptools\n',
                    #'sudo apt-get -y install python-pip\n',
                    'sudo apt-get -y install unzip\n',
                    'sudo apt-get -y install dnsmasq\n',
                    #'sudo wget -P /root https://s3.amazonaws.com/cloudformation'
                    #'-examples/aws-cfn-bootstrap-latest.tar.gz\n',
                    #'sudo mkdir -p /root/aws-cfn-bootstrap-latest\n',
                    #'sudo tar xvfz /root/aws-cfn-bootstrap-latest.tar.gz ',
                    #'--strip-components=1 -C /root/aws-cfn-bootstrap-latest\n',
                    #'sudo easy_install /root/aws-cfn-bootstrap-latest/\n',
                    #'sudo cfn-init -s \'', Ref('AWS::StackName'),
                    #'\' -r Ec2Instance -c ascending --region \'',
                    #Ref('AWS::Region'),
                    'sudo wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip\n',
                    'sudo wget -O /tmp/consul-ui.zip https://dl.bintray.com/mitchellh/consul/0.5.2_web_ui.zip\n',
                    'sudo unzip -n -d /bin /tmp/consul.zip\n',
                    'sudo unzip -n -d /var/consul/ui /tmp/consul-ui.zip\n',

                    '\n\n',
                    'sudo cat > /etc/consul/consul.json << EOM\n',
                    json.dumps(json_data),
                    '\nEOM\n',
                    'sudo mkdir -p /var/consul\n',
                    'sudo mkdir -p /var/consul/ui\n',
                    'sudo mkdir -p /var/consul/data\n',
                    'sudo mkdir -p /etc/consul\n',
                    'sudo cat > /etc/init/consul-server.conf << EOM\n'
                    'description "Consul server service"\n',
                    'start on runlevel [2345]\n',
                    'stop on runlevel [06]\n\n',
                    'exec consul agent -config-dir=/etc/consul\n'
                    '\nEOM\n'
                ])),

                #self.build_bootstrap([ConsulTemplate.BOOTSTRAP_SH], variable_declarations=startup_vars),

                Tags=Tags(Name=name, StackName=self.name)

            ))

    def get_cfn_config(self, config):
        return cloudformation.InitConfig(

                files=cloudformation.InitFiles({
                    "/tmp/puppet_agent_init.sh": cloudformation.InitFile(
                    content=EnvironmentBase.build_bootstrap(
                        ['user_data/rhel_puppet.sh',
                         'user_data/rhel_puppet_agent.sh'],
                        prepend_line='#!/bin/bash -x',
                        variable_declarations=['SERVER_NAME={}'.format('puppet.'+zone_name)]),
                    encoding='base64',
                    mode='000755')
                }),

                commands={
                    '1_run_puppet_agent_init': {
                        "cwd": "/tmp",
                        "command": "./puppet_agent_init.sh"
                    }
                }
            )


    def create_consul_sg(self):
        return self.add_resource(ec2.SecurityGroup('ConsulSecurityGroup',
            GroupDescription='Enables internal access to Consul',
            VpcId=Ref(self.vpc_id),
            SecurityGroupEgress=[
                ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [53, 8400, 8500, 8600]
            ] + [ec2.SecurityGroupRule(
                    IpProtocol=p, FromPort=8300, ToPort=8302, CidrIp="10.0.0.0/16"
                )
                for p in ['tcp', 'udp']
            ] + [ec2.SecurityGroupRule(
                    IpProtocol='udp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [53, 8400, 8500, 8600]
            ] + [ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, CidrIp="0.0.0.0/0"
                )
                for p in [80,443]
            ],
            SecurityGroupIngress= [ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [22, 53, 8400, 8500, 8600]
            ] + [
                ec2.SecurityGroupRule(
                    IpProtocol=p, FromPort=8300, ToPort=8302, CidrIp="10.0.0.0/16"
                )
                for p in ['tcp', 'udp']
            ] + [
                ec2.SecurityGroupRule(
                    IpProtocol='udp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [53, 8400, 8500, 8600]
            ],
            Tags=Tags(StackName=self.name)

        ))



class ConsulStackController(NetworkBase):
    """
    Coordinates CONSUL stack actions (create and deploy)
    """
    """
    Coordinates CONSUL stack actions (create and deploy)
    """
    #import pdb; pdb.set_trace()
    # When no config.json file exists a new one is created using the 'factory default' file.  This function
    # augments the factory default before it is written to file with the config values required by an ConsulTemplate
    @staticmethod
    def get_factory_defaults_hook():
        return ConsulTemplate.DEFAULT_CONFIG

    # When the user request to 'create' a new ELK template the config.json file is read in. This file is checked to
    # ensure all required values are present. Because ELK stack has additional requirements beyond that of
    # EnvironmentBase this function is used to add additional validation checks.
    @staticmethod
    def get_config_schema_hook():
        return ConsulTemplate.CONFIG_SCHEMA

    def __init__(self, *args, **kwargs):
        self.add_config_handler(ConsulTemplate)
        super(ConsulStackController, self).__init__(*args, **kwargs)

    def create_action(self):
        self.initialize_template()
        self.construct_network()
        self.add_child_template(bastion.Bastion())
        consul_config = self.config.get('consul')
        env_name = self.globals.get('environment_name', 'environmentbase-consul')
        consul_template = ConsulTemplate(env_name, consul_config.get('ami_id'), boto_config=self.config.get('boto'))
       # self.validate_cloudformation_template(self.to_json())

        self.add_child_template(consul_template)
        self.write_template_to_file()



    def validate_cloudformation_template(self, template_body):
        c = boto.connect_cloudformation()
        try:
            return c.validate_template(template_body=template_body)
        except boto.exception.BotoServerError as e:
            raise Exception(e.body)



def main():
    # This cli object takes the documentation comment at the top of this file (__doc__) and parses it against the
    # command line arguments (sys.argv).  Supported commands are create and deploy. The deploy function works fine as
    # is. ConsulStackController overrides the create action to include an ELK stack as an additional template.
    cli = CLI(doc=__doc__)
    ConsulStackController(view=cli)

if __name__ == '__main__':
    main()