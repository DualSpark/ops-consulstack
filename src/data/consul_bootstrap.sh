#sudo apt-get -y update
#sudo apt-get -y install unzip dnsmasq

#sudo apt-get -y install python-setuptools
#sudo apt-get -y install python-pip
sudo pip install https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz

sudo wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip
sudo wget -O /tmp/consul-ui.zip https://dl.bintray.com/mitchellh/consul/0.5.2_web_ui.zip


sudo mkdir -p /etc/consul
sudo mkdir -p /var/consul/data
sudo mkdir -p /var/consul/ui

sudo unzip -n -d /bin /tmp/consul.zip
sudo unzip -n -d /var/consul/ui /tmp/consul-ui.zip



cfn-init -s   -r Ec2Instance -c ascending




sudo cat > /etc/init/consul-server.conf << EOF
description "Consul server service"
start on runlevel [2345]
stop on runlevel [06]

exec consul agent -config-dir=/etc/consul -data-dir=/var/consul/data
EOF




echo "IP=$IP"
if [ "$IP" -eq "$JOIN" ] 
then
sudo cat > /etc/consul/consul.conf << EOF
{
    "bootstrap_expect": "$AZCOUNT",
    "start_join": ["10.0.16.4"],
    "server": true,
    "rejoin_after_leave": true,
    "enable_syslog": true,
    "data_dir": "/var/consul/data",
    "ui_dir": "/var/cosul/ui",
    "datacenter": "$REGION",
    "recursor": "10.0.0.2"
}
EOF
else
sudo cat > /etc/consul/consul.conf << EOF
{
    "start_join": ["10.0.16.4"],
    "server": true,
    "rejoin_after_leave": true,
    "enable_syslog": true,
    "data_dir": "/var/consul/data",
    "ui_dir": "/var/cosul/ui",
    "datacenter": "$REGION",
    "recursor": "10.0.0.2"
}
EOF

fi




sudo service consul-server start
sudo echo "server=/consul/127.0.0.1#8600" > /etc/dnsmasq.d/10-consul
sudo service dnsmasq restart
