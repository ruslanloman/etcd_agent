#!/usr/bin/env python2.7

import etcd
import json
import subprocess
import argparse
import os, signal
import pwd, grp
import time
import logging
import datetime
import shutil
from daemonize import Daemonize
from jsonschema import validate, exceptions
import tempfile

class Etcd_agent(Daemonize):
    def __init__(self, etcd_host, etcd_port, etcd_path, log_file, ssl=None):
        self._etcd_host = etcd_host
        self._etcd_port = etcd_port
        self._etcd_path = etcd_path
        self._ssl = ssl
        self._etcd_index = 0
        self.default_exec_timeout = 600
        self.flush_work_dir = True

        self.log = logging.getLogger('etcd_agent')
        self.fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=20971520, backupCount=4)
        self.fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(self.fh)
        self.log.setLevel(logging.INFO)

        super(Etcd_agent, self).__init__(app="Etcd_agent",
                                         pid='/var/run/etcd_agent.pid',
                                         action=self.run,
                                         keep_fds=[self.fh.stream.fileno()])

    def run(self):
        self.log.info('Starting etcd daemon...')
        self.client = etcd.Client(host=self._etcd_host, port=self._etcd_port, **self._ssl)
        while True:
            self.execute(self.get_action())
            time.sleep(5)

    def retry(self, func, *args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except etcd.EtcdConnectionFailed as e:
                self.log.error('Can\'t connect to etcd %s' % e)
            except etcd.EtcdKeyNotFound as e:
                self.log.error(e)
            time.sleep(30)

    def get_action(self):
        self.log.info('Retrive data from etcd')
        self.resp = self.retry(self.client.read, self._etcd_path)
        self.new_etcd_index = self.resp.etcd_index
        try:
           self.action = json.loads(self.resp.value)
        except ValueError as e:
           self.log.error('get_action failed %s' % e)
           self.action = False
        finally:
           self.log.info('Data info from etcd - %s' % self.action)
           return self.action

    def valid_json(self, data):
        schema = {
            'type': 'object',
            'properties': {
                  'action': {
                      'type': 'object',
                      'properties': {
                         'exec': {'type': 'array'},
                         'timeout': {'type': 'number'},
                      },
                      'required': ['exec', 'timeout']
                  },
            },
            'required': ['action']
        }
        try:
            validate(data, schema)
        except exceptions.ValidationError as e:
            self.log.error(e)
            return False
        else:
            return True

    def execute(self, data):
        self.log.info('OLD etcd_index - %d, NEW etcd_index - %d' % (self._etcd_index,
                                                                    self.new_etcd_index))
        if data and self.valid_json(data) and self._etcd_index != self.new_etcd_index:
            self._etcd_index = self.new_etcd_index
            self.exec_timeout = data['action'].get('timeout', self.default_exec_timeout)
            self.tmp_dir = tempfile.mkdtemp(prefix='etd_tmp')
            self.log.info('Creating workdir %s' % self.tmp_dir)
            for command in data['action'].get('exec'):
                self.log.info('Execute command - %s' % command)
                self.cmd(command)
            if self.flush_work_dir:
                shutil.rmtree(self.tmp_dir)

    def lock(self):
        pass

    def cmd(self, *args, **kwargs):
        self.uid = pwd.getpwnam(kwargs.get('uid', 'root')).pw_uid
        self.gid = grp.getgrnam(kwargs.get('uid', 'root')).gr_gid
        start = datetime.datetime.now()
        proc = subprocess.Popen(args, preexec_fn=lambda : (os.setegid(self.uid), os.seteuid(self.gid)),
                                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                           shell=True, cwd=self.tmp_dir)
        while proc.poll() is None:
            time.sleep(0.1)
            now =  datetime.datetime.now()
            if (now - start).seconds > self.exec_timeout:
                self.log.error('Process was killed due to exec_timeout - %d' % proc.pid)
                os.kill(proc.pid, signal.SIGKILL)
                os.waitpid(-1, os.WNOHANG)
                return None
        self.log.info('Command output - %s' % proc.stdout.read())
        self.exitcode = proc.wait()
        self.log.info('Exitcode of command - %s' % self.exitcode)
        return self.exitcode

def main():
    parser = argparse.ArgumentParser(description='etcd')
    parser.add_argument('--etcd-host', help='etcd host', default='127.0.0.1')
    parser.add_argument('--etcd-port', help='etcd port', default=4001)
    parser.add_argument('--etcd-path', help='etcd path', default='/etcd_agent')
    parser.add_argument('--ssl', help='Enable or Disable ssl', action='store_true')
    parser.add_argument('--ssl-ca', help='root ca cert')
    parser.add_argument('--ssl-cert', help='client cert')
    parser.add_argument('--ssl-key', help='client private key')
    parser.add_argument('--log-file', help='--log-file=/some/file', default='/var/log/etcd_agent.log')
    args = parser.parse_args()

    if args.ssl:
        ssl_options = {
            'protocol': 'https',
            'ca_cert': args.ssl_ca,
            'cert': (args.ssl_cert, args.ssl_key)
        }
    else:
        ssl_options = {
            'protocol': 'http',
        }


    Etcd_agent(
        etcd_host = args.etcd_host,
        etcd_port = args.etcd_port,
        etcd_path = args.etcd_path,
        log_file = args.log_file,
        ssl = ssl_options).start()

if __name__ == '__main__':
    main()

