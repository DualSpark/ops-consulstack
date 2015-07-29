import csv
import os


import boto
from troposphere import Ref, Tags, ec2


WILDCARD_CIDR = '0.0.0.0/0'

def create_subnet(template, name, vpc, cidr_block, availability_zone):
    return template.add_resource(ec2.Subnet(
        name,
        VpcId=Ref(vpc),
        CidrBlock=cidr_block,
        AvailabilityZone=availability_zone,
        Tags=Tags(Name=name)
    ))


def create_route_table(template, name, vpc, **attrs):
    return template.add_resource(ec2.RouteTable(
        name,
        VpcId=Ref(vpc),
        Tags=Tags(Name=name),
        **attrs
    ))


def create_route(template, name, route_table, cidr_block=None, **attrs):
    cidr_block = cidr_block or WILDCARD_CIDR
    return template.add_resource(ec2.Route(
        name,
        RouteTableId=Ref(route_table),
        DestinationCidrBlock=cidr_block,
        **attrs
    ))


def create_network_acl(template, name, vpc, **attrs):
    return template.add_resource(ec2.NetworkAcl(
        name,
        VpcId=Ref(vpc),
        Tags=Tags(Name=name),
        **attrs
    ))


def create_network_acl_entry(template, name, network_acl, rule_number,
                             port_range, rule_action='allow', egress=False,
                             protocol=6, cidr_block=None, **attrs):
    cidr_block = cidr_block or WILDCARD_CIDR
    return template.add_resource(ec2.NetworkAclEntry(
        name,
        NetworkAclId=Ref(network_acl),
        RuleNumber=rule_number,
        Protocol=protocol,
        RuleAction=rule_action,
        Egress=egress,
        CidrBlock=cidr_block,
        PortRange=ec2.PortRange(From=port_range[0], To=port_range[1]),
        **attrs
    ))


def create_security_group(t, name, description, vpc, ingress, egress, **attrs):
    return t.add_resource(ec2.SecurityGroup(
        name,
        GroupDescription=description,
        VpcId=Ref(vpc),
        SecurityGroupIngress=ingress,
        SecurityGroupEgress=egress,
        Tags=Tags(Name=name),
        **attrs
    ))

