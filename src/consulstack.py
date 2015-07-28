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
from troposphere import ec2, Tags, Ref, iam, GetAtt, Join, FindInMap, Output
from troposphere.ec2 import NetworkInterfaceProperty
from troposphere.sqs import Queue
from troposphere.autoscaling import Tag
import boto.vpc
import boto
import troposphere.autoscaling as autoscaling
import troposphere.elasticloadbalancing as elb
from environmentbase import resources
from environmentbase.patterns import bastion

class ConsulTemplate(Template):
    """
    Enhances basic template by adding elasticsearch, kibana and logstash services.
    """

    # Load USER_DATA scripts from package
    # E_BOOTSTRAP_SH = resources.get_resource('elasticsearch_bootstrap.sh', __name__)
    # L_BOOTSTRAP_SH = resources.get_resource('logstash_bootstrap.sh', __name__)
    # K_BOOTSTRAP_SH = resources.get_resource('kibana_bootstrap.sh', __name__)

    # default configuration values
    DEFAULT_CONFIG = {
        'consul': {
            'ami_id': 'amazonLinuxAmiId'
        }
    }

    NETWORK_CONFIG = {
        'network': {
            'az_count': 3,
            'public_subnet_count': 3,
            'private_subnet_count': 3
        }
    }

    # schema of expected types for config values
    CONFIG_SCHEMA = {
        'network': {
            'az_count': 'int',
            'public_subnet_count': 'int',
            'private_subnet_count': 'int'
        },
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
        self.create_consul_cluster(self.ami_id)


    def create_consul_cluster(self, ami_id):
        self.add_resource(ec2.Instance("ec2instance", InstanceType="m3.medium", ImageId=ami_id) )


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

    def get_config_network_hook():
        return ConsulTemplate.NETWORK_CONFIG


    # Override the default create action to construct an ELK stack
    def create_action(self):

        # Create the top-level cloudformation template
        self.initialize_template()

        # Attach the NetworkBase: VPN, routing tables, public/private subnets, NAT instances
        self.construct_network()

        self.add_child_template(bastion.Bastion())




        # Load some settings from the config file

        consul_config = self.config.get('consul')
        env_name = self.globals.get('environment_name', 'environmentbase-consul')


        # Create our ELK Template (defined above)
        consul_template = ConsulTemplate(env_name, consul_config.get('ami_id'))

        # Add the ELK template as a child of the top-level template
        # Note: This function modifies the incoming child template by attaching some standard inputs. For details
        # see ConsulTemplate.build_hook() above.
        # After parameters are added to the template it is serialized to file and uploaded to S3 (s3_utility_bucket).
        # Finally a 'Stack' resource is added to the top-level template referencing the child template in S3 and
        # assigning values to each of the input parameters.
        self.add_child_template(consul_template)

        # Serialize top-level template to file
        self.write_template_to_file()


def main():
    # This cli object takes the documentation comment at the top of this file (__doc__) and parses it against the
    # command line arguments (sys.argv).  Supported commands are create and deploy. The deploy function works fine as
    # is. ConsulStackController overrides the create action to include an ELK stack as an additional template.
    cli = CLI(doc=__doc__)
    ConsulStackController(view=cli)

if __name__ == '__main__':
    main()
