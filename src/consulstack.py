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
    Select
from troposphere.ec2 import NetworkInterfaceProperty
from troposphere.sqs import Queue
from troposphere.autoscaling import Tag
import boto.vpc
import boto
import troposphere.autoscaling as autoscaling
import troposphere.elasticloadbalancing as elb
from environmentbase import resources
from environmentbase.patterns import bastion
import template_utils as utils


class ConsulTemplate(Template):
    """
    Enhances basic template by adding elasticsearch, 
    kibana and logstash services.
    """

    # Load USER_DATA scripts from package
    BOOTSTRAP_SH = resources.get_resource('consul_bootstrap.sh', __name__)

    # default configuration values
    DEFAULT_CONFIG = {
        'consul': {
            'ami_id': 'ubuntu1404LtsAmiId',
        }
    }


    # schema of expected types for config values
    CONFIG_SCHEMA = {
        # 'network': {
        #     'az_count': 'int',
        #     'public_subnet_count': 'int',
        #     'private_subnet_count': 'int'
        # },
        'consul': {
            'ami_id': 'str'

        }
    }


    # Collect all the values we need to assemble our ELK stack
    def __init__(self, env_name, ami_id):
        super(ConsulTemplate, self).__init__('ConsulStack')
        self.env_name = env_name
        self.ami_id = ami_id
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

        for index in range(len(self.azs)):
            name = 'ConsulHost%s' % (index + 1)
            print "Creating instance {0}".format(name)
            #import pdb; pdb.set_trace()
            print "Configuring {0} with security group {1}".format(name, consul_security_group)
            print "Configuring {0} with security group {1}".format(name, self.common_security_group)
            consul_host = self.add_resource(ec2.Instance(
                name,
                InstanceType="m1.small",
                KeyName=Ref(self.parameters['ec2Key']),
                ImageId=FindInMap('RegionMap', Ref('AWS::Region'), self.ami_id),
                SecurityGroups=[Ref(consul_security_group)],
                NetworkInterfaces=[
                    ec2.NetworkInterfaceProperty(
                        Description='ENI for CONSUL hosts',
                        GroupSet=[Ref(consul_security_group)],
                        SubnetId=Ref(self.subnets['private'][index]),
                        AssociatePublicIpAddress=True,
                        DeviceIndex=0,
                        DeleteOnTermination=True
                    )
                ],

                Tags=Tags(Name=name)

            ))

    def create_consul_sg(self):
        return self.add_resource(ec2.SecurityGroup('ConsulSecurityGroup',
            GroupDescription='Enables internal access to Consul',
            VpcId=Ref(self.vpc_id),
            SecurityGroupEgress=[
                ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in [53, 80, 443, 8400, 8500, 8600]
            ] + [ec2.SecurityGroupRule(
                    IpProtocol=p, FromPort=8300, ToPort=8302, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in ['tcp', 'udp']
            ] + [ec2.SecurityGroupRule(
                    IpProtocol='udp', FromPort=p, ToPort=p, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in [53, 8400, 8500, 8600]
            ],
            SecurityGroupIngress= [ec2.SecurityGroupRule(
                    IpProtocol='tcp', FromPort=p, ToPort=p, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in [22, 53, 8400, 8500, 8600]
            ] + [
                ec2.SecurityGroupRule(
                    IpProtocol=p, FromPort=8300, ToPort=8302, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in ['tcp', 'udp']
            ] + [
                ec2.SecurityGroupRule(
                    IpProtocol='udp', FromPort=p, ToPort=p, 
                    SourceSecurityGroupId=Ref(self.common_security_group)
                )
                for p in [53, 8400, 8500, 8600]
            ]
        ))



class ConsulStackController(NetworkBase):
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

    # def get_config_network_hook():
    #     return ConsulTemplate.NETWORK_CONFIG

    def create_action(self):
        self.initialize_template()
        self.construct_network()
        self.add_child_template(bastion.Bastion())
        consul_config = self.config.get('consul')
        env_name = self.globals.get('environment_name', 'environmentbase-consul')
        consul_template = ConsulTemplate(env_name, consul_config.get('ami_id'))
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