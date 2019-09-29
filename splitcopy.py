#!/usr/bin/env python3
""" splits a given file into peices in a tmp directory, copies these to a junos
    host then reassembles them. Tested to be 15x faster to transfer an 845MB
    file than regular scp

    Requires 'system services ssh' configuration on remote host
    Requires python 3.4+ to run.
        3x faster in 3.6 than 3.4

    install required module via:
        pip3 install junos-eznc
"""

import sys
if (sys.version_info[0] < 3 or
        (sys.version_info[0] == 3 and sys.version_info[1] < 4)):
    raise Exception("Python 3.4 or later required")

import argparse
import asyncio
import os
import contextlib
import datetime
import fnmatch
import functools
import re
import shutil
import tempfile
from subprocess import call
from jnpr.junos import Device
from jnpr.junos.utils.scp import SCP
from jnpr.junos.utils.start_shell import StartShell

def main():
    """
    Generic main() statement
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', nargs=1,
                        help='user to authenticate on remote host')
    parser.add_argument('--password', nargs=1,
                        help='password to authenticate on remote host')
    parser.add_argument('--host', nargs=1,
                        help='remote host to connect to')
    parser.add_argument('filepath',
                        help='Path to filename to work on')
    args = parser.parse_args()
    if not (args.user and args.password and args.host):
        print("must specify --host, --user and --password args")
        sys.exit(1)

    print("script started at {}".format(datetime.datetime.now()))

    host = args.host[0]
    user = args.user[0]
    password = args.password[0]

    if re.search('/', args.filepath):
        file_name = args.filepath.rsplit('/', 1)[1]
    else:
        file_name = args.filepath

    if args.filepath + ".sha1":
        sha1file = open(args.filepath + ".sha1", "r")
        orig_sha1 = sha1file.read().rstrip()
    else:
        sha1_str = call("sha1sum {}".format(args.filepath))
        orig_sha1 = sha1_str.split(" ")[0]
    file_size = os.path.getsize(args.filepath)
    split_size = divmod(file_size, 20)[0]

    with tempdir():
        call("split -b {} {} {}"
             .format(split_size, args.filepath, file_name), shell=True)
        sfiles = []
        for sfile in os.listdir('.'):
            if fnmatch.fnmatch(sfile, '{}*'.format(file_name)):
                sfiles.append(sfile)
        dev = Device(host=host, user=user, passwd=password)
        with StartShell(dev) as s_sh:
            s_sh.run("rm -rf /var/tmp/splitcopy_{}".format(file_name))
            s_sh.run("mkdir /var/tmp/splitcopy_{}".format(file_name))
            if not s_sh.last_ok:
                print("unable to create the tmp directory -"
                      " is there sufficient disk space on remote host?,"
                      " exiting")
                sys.exit(1)
            loop = asyncio.get_event_loop()
            tasks = []
            for sfile in sfiles:
                task = loop.run_in_executor(None,
                                            functools.partial(scp_put,
                                                              dev,
                                                              sfile,
                                                              file_name))
                tasks.append(task)
            loop.run_until_complete(asyncio.gather(*tasks))
            loop.close()
            s_sh.run("cat /var/tmp/splitcopy_{}/* > /var/tmp/{}"
                     .format(file_name, file_name))
            s_sh.run("rm -rf /var/tmp/splitcopy_{}"
                     .format(file_name))
            if not s_sh.last_ok:
                print("unable to delete the tmp directory on remote host,"
                      " delete it manually")
            if s_sh.run("ls /var/tmp/{}".format(file_name)):
                sha1_tuple = s_sh.run("sha1 /var/tmp/{}".format(file_name))
                new_sha1 = (sha1_tuple[1].split("\n")[1].split(" ")[3].rstrip())
                if orig_sha1 == new_sha1:
                    print("file has been successfully copied to {}:/var/tmp/{}"
                          ", sha1 matches".format(host, file_name))
                else:
                    print("file has been copied to {}:/var/tmp/{}, but the "
                          "sha1 does not match - please retry"
                          .format(host, file_name))
            else:
                print("file {}:/var/tmp/{} not found! please retry"
                      .format(host, file_name))
            dev.close()
            print("script ended at {}".format(datetime.datetime.now()))

def scp_put(dev, sfile, file_name):
    """ copies file to remote host via scp
    Args:
        dev - the ssh connection handle
        sfile(str) - name of the file to copy
        file_name(str) - part of directory name
    Returns:
        None
    Raises:
        None
    """
    with SCP(dev, progress=True) as scp:
        scp.put(sfile, "/var/tmp/splitcopy_{}/".format(file_name))

@contextlib.contextmanager
def change_dir(newdir, cleanup=lambda: True):
    """ cds into temp directory.
        Upon script exit, changes back to original directory
        and calls cleanup() to delete the temp directory
    Args:
        newdir(str) - path to temp directory
        cleanup(?) - pointer to cleanup function ?
    Returns:
        None
    Raises:
        None
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)
        cleanup()

@contextlib.contextmanager
def tempdir():
    """
    creates a temp directory
    defines how to delete directory upon script exit
    Args:
        None
    Returns:
        dirpath(str): path to temp directory
    Raises:
        None
    """
    dirpath = tempfile.mkdtemp()
    def cleanup():
        """ deletes temp dir
        """
        shutil.rmtree(dirpath)
    with change_dir(dirpath, cleanup):
        yield dirpath

if __name__ == '__main__':
    main()
