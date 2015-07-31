sudo apt-get -y update
sudo apt-get -y install unzip dnsmasq


sudo wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip
sudo wget -O /tmp/consul-ui.zip https://dl.bintray.com/mitchellh/consul/0.5.2_web_ui.zip


JOIN="10.0.16.4"
CONFIG="/etc/consul"
DATA="/var/consul/data"
UI="/var/consul/ui"

IP=`sudo hostname -i`
echo "$CIP"
sudo mkdir -p "$CONFIG"
sudo mkdir -p "$DATA"
sudo mkdir -p "$UI"

sudo unzip -n -d /bin /tmp/consul.zip
sudo unzip -n -d "$UI" /tmp/consul-ui.zip
BOOTSTRAP=""
SERVER=""

echo "IP=$IP"
if [ "$IP" = "$JOIN" ]
then
	$BOOSTRAP="\"bootstrap_expect\": 3",
fi

if [ "$IP" != "$JOIN" ]
then
	$SERVER="\"start_join\": [\"$JOIN\"]",
fi

echo "BOOTSTRAP=$BOOTSTRAP"
echo "SERVER=$SERVER"

sudo cat > /etc/consul/consul.json <<- EOM
{
	$BOOTSTRAP
    $SERVER
 	#   {% endif %}
    "server": true,
    "rejoin_after_leave": true,
    "enable_syslog": true,
    "data_dir": "$DATA",
    "ui_dir": "$UI",
    "datacenter": "$REGION",
    "recursor": "10.0.0.2"
}
EOM

sudo cat > /etc/init/consul-server.conf <<- EOM
description "Consul server service"
start on runlevel [2345]
stop on runlevel [06]





exec consul agent -config-dir=/etc/consul
EOM

sudo service consul-server start
sudo echo "server=/consul/127.0.0.1#8600" > /etc/dnsmasq.d/10-consul
sudo service dnsmasq restart
