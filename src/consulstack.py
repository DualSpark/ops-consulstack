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
from troposphere import ec2, Tags, Ref, iam, GetAtt, Join, \
Select, Base64, FindInMap, Output
from troposphere.cloudformation import WaitCondition, WaitConditionHandle
import boto.vpc
import boto
import json
from environmentbase import resources
from environmentbase.patterns import bastion
from pprint import pprint


class ConsulTemplate(Template):

    # When no config.json file exists a new one is created using the 'factory default' file.  This function
    # augments the factory default before it is written to file with the config values required by an ConsulTemplate
    @staticmethod
    def get_factory_defaults():
        return {'consul': {
            's_ami_id': 'ubuntu1404LtsAmiId',
            'a_ami_id': 'ubuntu1404LtsAmiId',
            'service_ami_id': 'ubuntu1404LtsAmiId'

            },
            'atlas': {
                'atlas-username': '',
                'atlas-token': ''

            }
        }

    @staticmethod
    def get_config_schema():
        return {'consul': {
            's_ami_id': 'str',
            'a_ami_id': 'str',
            'service_ami_id': 'str',

            },
            'atlas': {
                'atlas-username': 'str',
                'atlas-token': 'str'

            }
        }

    # Collect all the values we need to assemble our Consul.io stack
    def __init__(self, env_name, s_ami_id, service_ami_id, boto_config={}, atlas_config={}):
        super(ConsulTemplate, self).__init__('Consul')
        self.env_name = env_name
        self.s_ami_id = s_ami_id
        self.service_ami_id = service_ami_id
        self.boto_config = boto_config
        self.atlas_config = atlas_config
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
        startup_vars.append(Join('=', ['AZCOUNT', len(self.azs)]))

        #Array to hold predefined IPs for our consul host
        p_ids = []

        for index in range(len(self.azs)):
            p_ids.append("10.0.%s.4" % ((16 + 16) * (index+1)))


        delim = '\n'
        #Grab our consul.conf file to distribute to nodes
        with open('templates/consul.json') as json_file:
            json_data = json.load(json_file)

        #Grab our consul.conf file to distribute to nodes
        #with open('templates/consul-mysql.json') as json_file:
        #    d_json_data = json.load(json_file)
        with open('templates/consul-web.json') as json_file:
            w_json_data = json.load(json_file)
        with open('templates/ping.json') as json_file:
            p_json_data = json.load(json_file)


        atlas_username = ''
        atlas_token = ''



        #Loop over the AZs for our region
        for index in range(len(self.azs)):

            #Add in our consul defaults for the various configs we need
            #to write to our nodes
            json_data['server'] = True
            json_data['start_join'] = p_ids
            json_data['data_dir'] = '/var/consul/data'
            json_data['ui_dir'] = '/var/consul/ui'
            json_data['datacenter'] = "dc1"
            json_data['encrypt'] = 'Z+QYrQRxLf/RgFL64dnCNA=='
            #startup_vars.append(Join('=', ['IP', p_ids[index]]))

            #If the index is 0 we are at our bootstrap machine.
            #Clear out start_join param and set bootstrap_expect
            #to the number of AZs
            if(index == 0):
                json_data['bootstrap_expect'] = len(self.azs)
                if(json_data.get('start_join')):
                    del json_data['start_join']
                consul_ec2_name = 'consulclusterserverleader'
                #import pdb; pdb.set_trace()
                if(self.atlas_config.get('atlas-username')):
                    atlas_username = "-atlas %s " % self.atlas_config.get('atlas-username')
                    if(self.atlas_config.get('atlas-token')):
                        atlas_token = "-atlas-token %s " % self.atlas_config.get('atlas-token')

            #This is reg node in the cluster
            #Remove bootstrap config
            #add join config for nodes excluding their own IP
            else:
                ohosts = []
                if(json_data.get('bootstrap_expect')):
                    del json_data['bootstrap_expect']
                for i in p_ids:
                    if(i == p_ids[index]):
                        continue
                    else:
                        ohosts.append(i)
                json_data['start_join'] = ohosts
                consul_ec2_name = 'consulclusterserver%s' % index


            consul_host = self.add_resource(ec2.Instance(
                consul_ec2_name,
                InstanceType="m1.small",
                KeyName=Ref(self.parameters['ec2Key']),
                ImageId=FindInMap('RegionMap', Ref('AWS::Region'), self.s_ami_id),
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
                    'sudo apt-get update\n',
                    'sudo apt-get -y install unzip\n',
                    'sudo apt-get -y install dnsmasq\n',
                    'sudo mkdir -p /var/consul\n',
                    'sudo mkdir -p /var/consul/ui\n',
                    'sudo mkdir -p /var/consul/data\n',
                    'sudo mkdir -p /etc/consul\n',
                    # 'sudo hostnamectl set-hostname ',
                    # consul_ec2_name,
                    # '\n',
                    'sudo wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip\n',
                    'sudo wget -O /tmp/consul-ui.zip https://dl.bintray.com/mitchellh/consul/0.5.2_web_ui.zip\n',
                    'sudo unzip -n -d /bin /tmp/consul.zip\n',
                    'sudo unzip -n -d /var/consul/ui /tmp/consul-ui.zip\n',
                    '\n\n',
                    'sudo cat > /etc/consul/consul.json << EOM\n',
                    json.dumps(json_data, indent=4, sort_keys=True).strip(),
                    '\nEOM\n',
                    'sudo cat > /etc/init/consul-server.conf << EOM\n'
                    'description "Consul server service"\n',
                    'start on (local-filesystems and net-device-up IFACE=eth0)\n',
                    'stop on runlevel [!12345]\n\n',
                    'respawn\n\n',
                    'exec consul agent -server -config-dir=/etc/consul ',
                    atlas_username,
                    atlas_token,
                    '\nEOM\n',
                    'sudo service consul-server start\n\n'
                ])),


                Tags=Tags(Name=consul_ec2_name, StackName=self.name)

            ))


            if(index == 0):
                consul_cluster_leader = consul_host



            json_data['start_join'] = [p_ids[index]]

            if(json_data.get('bootstrap_expect')):
                del json_data['bootstrap_expect']

            json_data["server"] = False

            consul_client = self.add_resource(ec2.Instance(
                'consulclient%s' % index,
                InstanceType="m1.small",
                KeyName=Ref(self.parameters['ec2Key']),
                SubnetId=self.subnets['private'][index],
                SecurityGroupIds=[Ref(consul_security_group)],
                ImageId=FindInMap('RegionMap', Ref('AWS::Region'), self.service_ami_id),
                DependsOn=consul_ec2_name,
                UserData=Base64(Join('', [
                    '#!/bin/bash\n\n',
                    'sudo apt-get -y update\n',
                    'sudo apt-get -y install unzip nginx\n',
                    'sudo service nginx start\n\n',
                    # 'sudo apt-get -y install unzip\n',
                    'mkdir -p /var/consul\n',
                    'mkdir -p /var/consul/data\n',
                    'mkdir -p /etc/consul\n',
                    '\n',
                    'wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip\n',
                    'unzip -n -d /bin /tmp/consul.zip\n',
                    '\n\n',
                    'cat > /etc/consul/consul.json << EOM\n',
                    json.dumps(json_data, indent=4, sort_keys=True).strip(),
                    '\nEOM\n',
                    'cat > /etc/consul/consul-web.json << EOM\n',
                    json.dumps(w_json_data, indent=4, sort_keys=True).strip(),
                    '\nEOM\n',
                    'cat > /etc/init/consul-agent.conf << EOM\n'
                    'description "Consul agent service"\n',
                    'start on (local-filesystems and net-device-up IFACE=eth0)\n',
                    'stop on runlevel [!12345]\n\n',
                    'respawn\n\n',
                    'exec consul agent -data-dir=/var/consul/data -config-dir=/etc/consul\n'
                    '\nEOM\n',
                    'sudo service consul-agent start\n\n',

                ])),


                Tags=Tags(Name='consulclient%s' % index, StackName=self.name)

            ))



        self.add_output([
            Output(
                "ConsulClusterLeader",
                Description="Consul Cluster Leader IP",
                Value=GetAtt(consul_cluster_leader, 'PrivateIp'),
                )
            ])




    def create_consul_sg(self):
        return self.add_resource(ec2.SecurityGroup('ConsulSecurityGroup',
            GroupDescription='Enables internal access to Consul',
            VpcId=Ref(self.vpc_id),
            SecurityGroupEgress=[
                ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [22, 53, 7223, 8400, 8500, 8600]
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
                for p in [80,443, 7223]
            ],
            SecurityGroupIngress= [ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, CidrIp="10.0.0.0/16"
                )
                for p in [22, 80, 443, 53, 8400, 8500, 8600]
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
        atlas_config = self.config.get('atlas')
        env_name = self.globals.get('environment_name', 'environmentbase-consul')
        consul_template = ConsulTemplate(env_name, consul_config.get('s_ami_id'), consul_config.get('service_ami_id'), boto_config=self.config.get('boto'), atlas_config=self.config.get('atlas'))

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
    # is. ConsulStackController overrides the create action to include an Consul.io stack as an additional template.
    cli = CLI(doc=__doc__)
    ConsulStackController(view=cli)

if __name__ == '__main__':
    main()