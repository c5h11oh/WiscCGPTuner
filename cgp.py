# Utilities
import os, time
import shlex
import glob
# Bayesian Optimization
import GPy
import numpy as np
import GPyOpt
from GPyOpt.methods import BayesianOptimization
# Configurations
from config.cgp_configs import *

def send_cmd(cmd, background=False):
    ssh_cmd = 'ssh {} {}'.format(database, shlex.quote(cmd))
    if (background):
        ssh_cmd += ' &'
    print(ssh_cmd)
    os.system(ssh_cmd)
    # os.system(cmd)

def return_to_default():
    # OS param - kernel, vm
    os_kn_vm_cmd = 'sudo sysctl kernel.sched_latency_ns={} kernel.sched_migration_cost_ns={} vm.dirty_background_ratio={} vm.dirty_ratio={} vm.min_free_kbytes={} vm.vfs_cache_pressure={}'.format(
        default['sched_latency_ns'],
        default['sched_migration_cost_ns'],
        default['dirty_background_ratio'],
        default['dirty_ratio'],
        default['min_free_kbytes'],
        default['vfs_cache_pressure'],
    )
    send_cmd(os_kn_vm_cmd)

    # OS param - network
    # TODO: reset RFS

    # OS param - storage
    storage_cmds = [
        # 'sudo sed -i \'s/{}/{}/\' /etc/fstab'.format(noatime_conf['open'],noatime_conf['close']),
        'sudo bash -c "echo {} > /sys/block/{}/queue/nr_requests"'.format(default['nr_requests'], block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/scheduler"'.format(schedulers[default['scheduler']], block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/read_ahead_kb"'.format(default['read_ahead_kb'], block_device),
    ]
    for cmd in storage_cmds:
        send_cmd(cmd)

def setup_system_params(x):
    # OS param - kernel, vm
    sched_latency_ns = str(x[0, 4])
    sched_migration_cost_ns = str(x[0, 5])
    dirty_background_ratio = str(x[0, 6])
    dirty_ratio = str(x[0, 7])
    min_free_kbytes = str(x[0, 8])
    vfs_cache_pressure = str(x[0, 9])
    
    os_kn_vm_cmd = 'sudo sysctl kernel.sched_latency_ns={} kernel.sched_migration_cost_ns={} vm.dirty_background_ratio={} vm.dirty_ratio={} vm.min_free_kbytes={} vm.vfs_cache_pressure={}'.format(
        sched_latency_ns,
        sched_migration_cost_ns,
        dirty_background_ratio,
        dirty_ratio,
        min_free_kbytes,
        vfs_cache_pressure,
    )

    send_cmd(os_kn_vm_cmd)

    # OS param - network
    RFS = bool(x[0, 10])
    rps_sock_flow_entries = 32768 if RFS else 0
    rps_cmds = [
        f'sudo bash -c "echo {rps_sock_flow_entries} > /proc/sys/net/core/rps_sock_flow_entries"'
    ]
    rx_queues_dirs = glob.glob(f'/sys/class/net/{network_device}/queues/rx-*/')
    network_num_queues = len(rx_queues_dirs)
    for rx_queues_dir in rx_queues_dirs:
        rps_cmds.append(
            f'sudo bash -c "echo {rps_sock_flow_entries // network_num_queues} > {rx_queues_dir}rps_flow_cnt"'
        )
    for cmd in rps_cmds:
        send_cmd(cmd)

    # OS param - storage
    # noatime = bool(x[0, 11])
    nr_requests = str(x[0, 12])
    scheduler = schedulers[x[0, 13]]
    read_ahead_kb = str(x[0, 14])

    storage_cmds = [
        # 'sudo sed -i \'s/{old}/{new}/\' /etc/fstab'.format(
        #     old=(noatime_conf['close'] if noatime else noatime_conf['open']),
        #     new=(noatime_conf['open'] if noatime else noatime_conf['close'])
        # ),
        'sudo bash -c "echo {} > /sys/block/{}/queue/nr_requests"'.format(nr_requests, block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/scheduler"'.format(scheduler, block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/read_ahead_kb"'.format(read_ahead_kb, block_device),
    ]

    for cmd in storage_cmds:
        send_cmd(cmd)


def f_mongo(x):
    """
    input: configuration + workload x
    output: mean response time R (ms)
    """
    # sanity check
    if (x[0, 15] < 0 or x[0,15] > 2):
        raise ValueError()
    if (x[0, 16] == 0):
        raise ValueError()
    # TODO: others?

    # setup system params (OS, network, storage)
    setup_system_params(x)

    # mount storage at /db
    mount_cmd = 'sudo mount -o defaults' + (',noatime' if bool(x[0, 11]) else '') + f' /dev/{block_device} /db'
    send_cmd(mount_cmd)

    # init MongoDB with params
    
    # wiredTigerCacheSizeGB = str(x[0, 0])
    # eviction_dirty_target = str(x[0, 1])
    # eviction_dirty_trigger = str(x[0, 2])
    # syncdelay = str(x[0, 3])
    db_cmd = f'mongod --dbpath={mongo_dir}/db --logpath={mongo_dir}/log/log.log --bind_ip localhost,{database}'
    if (x[0,0] != 0) :
        db_cmd += f' --wiredTigerCacheSizeGB {x[0, 0]} --wiredTigerEngineConfigString "eviction_dirty_target={x[0, 1]},eviction_dirty_trigger={x[0, 2]}" --setParameter syncdelay={x[0, 3]}'
    db_cmd += ' &'
    ## mongod will run in background (&)
    send_cmd(db_cmd, True)
    time.sleep(2)

    # drop previous collection if exists
    drop_coll_cmd = 'mongo --host {} --eval "db.getMongo().getDB(\'ycsb\').usertable.drop()"'.format(database)
    os.system(drop_coll_cmd)

    # load workload (on server 'database')
    wl_mix = chr(ord('a') + x[0, 15]) # [0, 1, 2] => ['a', 'b', 'c']
    wl_thd = x[0, 16]
    ycsb_load_cmd = f'{ycsb_path}/bin/ycsb load mongodb -threads {db_cpu} -s -P {ycsb_path}/workloads/workload{wl_mix}'
    for k, v in ycsb_params.items():
        ycsb_load_cmd += f' -p {k}={v}'
    send_cmd(ycsb_load_cmd)

    # run YCSB (from this server 'ycsb')
    ycsb_run_cmd = f'{ycsb_path}/bin/ycsb run mongodb -threads {wl_thd} -P {ycsb_path}/workloads/workload{wl_mix} -p mongodb.url=mongodb://{database}:27017/ycsb >> ycsb_result'
    for k, v in ycsb_params.items():
        ycsb_run_cmd += f' -p {k}={v}'
    os.system(ycsb_run_cmd)
    # TODO: get return value

    # stop MongoDB
    send_cmd('pkill mongod')

    # unmount /db
    send_cmd(f'sudo umount /dev/{block_device}')

    # reset params (optional)
    return_to_default()

    # TODO:
    # return XXXXXXX

x = np.array([[
    # DB param
    0,
    0,
    0,
    0,
    # OS param - kernel, vm
    default['sched_latency_ns'],
    default['sched_migration_cost_ns'],
    default['dirty_background_ratio'],
    default['dirty_ratio'],
    default['min_free_kbytes'],
    default['vfs_cache_pressure'],
    # OS param - network
    0, # RFS
    # OS param - storage
    default['noatime'],
    default['nr_requests'],
    default['scheduler'],
    default['read_ahead_kb'],
    # workload
    0,
    0,
]])
f_mongo(x)
# return_to_default()
