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
    def __init__(self, etcd_host, etcd_port, etcd_path, log_file):
        self._etcd_host = etcd_host
        self._etcd_port = etcd_port
        self._etcd_path = etcd_path
        self._etcd_index = 0

        self.log = logging.getLogger('etcd_agent')
        self.fh = logging.FileHandler(log_file, 'w')
        self.fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(self.fh)
        self.log.setLevel(logging.INFO)

        super(Etcd_agent, self).__init__(app="Etcd_agent",
                                         pid='/var/run/etcd_agent.pid',
                                         action=self.run,
                                         keep_fds=[self.fh.stream.fileno()])

    def run(self):
        self.log.info('Starting etcd daemon...')
        self.client = etcd.Client(host=self._etcd_host, port=self._etcd_port)
        while True:
            self.execute(self.get_action())
            time.sleep(5)

    def retry(self, func, *args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except (etcd.EtcdKeyNotFound, etcd.EtcdConnectionFailed) as e:
                self.log.error('Try to get data from etcd %s' % e)

    def get_action(self):
        self.log.info('Retrive data from etcd')
        self.resp = self.retry(self.client.read, self._etcd_path)
        try:
           self.new_etcd_index = self.resp.etcd_index
           self.action = json.loads(self.resp.value)
        except (ValueError, etcd.EtcdKeyNotFound, etc.EtcdConnectionFailed) as e:
           self.log.error('get_action failed %s' % e)
           self.action = False
        finally:
           self.log.info('Data info from etcd - %s' % self.action)
           return self.action

    def execute(self, data):
        self.log.info('OLD etcd_index - %d, NEW etcd_index - %d' % (self._etcd_index,
                                                                    self.new_etcd_index))
        if data and self._etcd_index != self.new_etcd_index:
            self._etcd_index = self.new_etcd_index
            for command in data['action']['exec']:
                self.log.info('Execute command - %s' % command)
                self.cmd(command)

    def lock(self):
        pass

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
    parser.add_argument('--log-file', dest='log_file', help='--log-file=/some/file', default='/var/log/etcd_agent.log')
    args = parser.parse_args()

    Etcd_agent(args.etcd_host, args.etcd_port, args.etcd_path, args.log_file).start()

if __name__ == '__main__':
    main()

