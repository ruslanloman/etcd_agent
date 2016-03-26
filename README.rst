########################
== Installation ==
For Amazon/CentOS distrib:
  * yum install python27-pip puppet3 git && git clone https://github.com/ruslanloman/etcd_agent.git
  * pip install -r requirements.txt
  * cp etcd_agent.py /usr/local/bin/ && cp init.d/amazon_etcd_agent /etc/init.d/etcd_agent
  * Add /etc/default/etcd_agent.ini or pass this data via cloud-init
    etcd_host=my-etcd-host.example.com
    etcd_path=/agent-task
    -- add ssl certs if required
    ca=/etc/ssl/cacert.pem
    cert=/etc/ssl/cert.pem
    key=/etc/ssl/key.pem
  * /sbin/chkconfig --add etcd_agent && /sbin/chkconfig etcd_agent on
  * service etcd_agent start

For Ubuntu distrib
  * git clone https://github.com/ruslanloman/etcd_agent.git && apt-get install puppet python-pip && service puppet stop
  * cd pip install -r requirements.txt
  * cp etcd_agent.py /usr/local/bin/ && cp init.d/ubuntu_etcd_agent /etc/init.d/etcd_agent
  * Add /etc/default/etcd_agent.ini or pass this data via cloud-init
    etcd_host=my-etcd-host.example.com
    etcd_path=/agent-task
    -- add ssl certs if required
    ca=/etc/ssl/cacert.pem
    cert=/etc/ssl/cert.pem
    key=/etc/ssl/key.pem
  * upload correct cert,ca and key to /etc/ssl files
  * update-rc.d etcd_agent defaults && update-rc.d etcd_agent enable
  * service etcd_agent start

== Example of task.yaml ==
---
action:
    exec:
      - 'bash -c "echo Action1"'
      - 'bash -c "echo Action2"'
    timeout: 600
------------------------------------------------
== Upload task.yaml to etcd service ==

#!/usr/bin/env python2.7
import etcd, yaml, json

data = yaml.load(open('task.yaml', 'r').read())
client = etcd.Client('my-etcd-host.example.com')
client.write('/agent-task', json.dumps(data))
------------------------------------------------
  * Check etcd_agent log to find output from command exectution, log path '/var/log/etc_agent'
