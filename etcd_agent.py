#!/usr/bin/env python2.7

import etcd
import json
import subprocess
import argparse
import os
import pwd
import grp
import time
import logging
from daemonize import Daemonize

class Etcd_agent(Daemonize):
    def __init__(self, etcd_host, etcd_port, etcd_path):
        self._etcd_host = etcd_host
        self._etcd_port = etcd_port
        self._etcd_path = etcd_path
        self._etcd_index = 0

        self.log = logging.getLogger('etcd_agent')

        super(Etcd_agent, self).__init__(app="Etcd_agent",
                                         pid='/var/run/etcd_agent.pid',
                                         action=self.run)

    def run(self):
        self.client = etcd.Client(host=self._etcd_host, port=self._etcd_port)
        self.log.info('Starting etcd daemon...')
        while True:
            self.execute(self.get_action())
            time.sleep(5)

    def get_action(self):
        self.log.info('Retrive data from etcd')
        try:
           self.resp = (self.client.read(self._etcd_path))
           self.new_etcd_index = self.resp.etcd_index
           self.action = json.loads(self.resp.value)
        except (ValueError, etcd.EtcdKeyNotFound) as e:
           self.action = False
        finally:
           self.log.info('Data info from etcd - %s' % self.action)
           return self.action

    def execute(self, data):
        if data and self._etcd_index != self.new_etcd_index:
            self._etcd_index = self.new_etcd_index
            for command in data['action']['exec']:
                self.log.info('Execute command - %s' % command)
                self.cmd(command)

    def cmd(self, *args, **kwargs):
        self.uid = pwd.getpwnam(kwargs.get('uid', 'root')).pw_uid
        self.gid = grp.getgrnam(kwargs.get('uid', 'root')).gr_gid
        proc = subprocess.Popen(args, preexec_fn=lambda : (os.setegid(self.uid), os.seteuid(self.gid)),
                                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell = True)
        self.log.info('Command output - %s' % proc.stdout.read())
        self.exitcode = proc.wait()
        self.log.info('Exitcode of command - %s' % self.exitcode)
        return self.exitcode

def main():
    parser = argparse.ArgumentParser(description='etcd')
    parser.add_argument('--etcd_host', help='etcd host', required=True)
    parser.add_argument('--etcd_port', help='etcd port', default=4001)
    parser.add_argument('--etcd_path', help='etcd path', default='/etcd_agent')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename='/var/log/etcd_agent.log',
                        filemode='w')

    Etcd_agent(args.etcd_host, args.etcd_port, args.etcd_path).run()

if __name__ == '__main__':
    main()

