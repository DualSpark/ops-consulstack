sudo apt-get -y update
sudo apt-get -y install unzip dnsmasq


sudo wget -O /tmp/consul.zip https://dl.bintray.com/mitchellh/consul/0.5.2_linux_amd64.zip
sudo wget -O /tmp/consul-ui.zip https://dl.bintray.com/mitchellh/consul/0.5.2_web_ui.zip


sudo unzip -n -d /bin /tmp/consul.zip
sudo unzip -n -d /var/consul/ui /tmp/consul-ui.zip

sudo mkdir -p /etc/consul
sudo mkdir -p /var/consul/data
sudo cp templates/consul.json /etc/consul/consul.json
sudo cp files/consul-server.conf /etc/init/consul-server.conf
sudo service consul-server start

sudo echo "server=/consul/127.0.0.1#8600" > /etc/dnsmasq.d/10-consul
sudo service dnsmasq restart
