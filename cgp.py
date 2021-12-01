#Import Modules
import os, sys
import GPy
import numpy as np
#GPyOpt - Cases are important, for some reason
import GPyOpt
from GPyOpt.methods import BayesianOptimization
from config.cgp_configs import *

def return_to_default():
    os_kn_vm_cmd = 'sudo sysctl kernel.sched_latency_ns={} kernel.sched_migration_cost_ns={} vm.dirty_background_ratio={} vm.dirty_ratio={} vm.min_free_kbytes={} vm.vfs_cache_pressure={}'.format(
        default['sched_latency_ns'],
        default['sched_migration_cost_ns'],
        default['dirty_background_ratio'],
        default['dirty_ratio'],
        default['min_free_kbytes'],
        default['vfs_cache_pressure'],
    )
    storage_cmds = [
        'sudo sed -i \'s/{}/{}\t0 1/\' /etc/fstab'.format(noatime_conf['open'],noatime_conf['close']),
        'sudo bash -c "echo {} > /sys/block/{}/queue/nr_requests"'.format(default['nr_requests'], block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/scheduler"'.format(schedulers[default['scheduler']], block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/read_ahead_kb"'.format(default['read_ahead_kb'], block_device),
    ]

    for cmd in storage_cmds:
        os.system(cmd)

def f_mongo(x):
    # DB param
    wiredTigerCacheSizeGB = x[0, 0]
    eviction_dirty_target = x[0, 1]
    eviction_dirty_trigger = x[0, 2]
    syncdelay = x[0, 3]

    db_cmd = f'mongod --dbpath={mongo_dir}/db --logpath={mongo_dir}/log/log.log --wiredTigerCacheSizeGB {wiredTigerCacheSizeGB} --wiredTigerEngineConfigString "eviction_dirty_target={eviction_dirty_target},eviction_dirty_trigger={eviction_dirty_trigger}" --setParameter syncdelay={syncdelay}'.format(
        wiredTigerCacheSizeGB=str(wiredTigerCacheSizeGB),
        eviction_dirty_target=str(eviction_dirty_target),
        eviction_dirty_trigger=str(eviction_dirty_trigger),
        syncdelay=str(syncdelay)
    )
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

    # os.system(os_kn_vm_cmd)

    # OS param - network
    RFS = str(x[0, 10]) != 0
    rps_sock_flow_entries = 32768 if RFS else 0
    device = 'lo'
    num_queues = 1
    rps_cmds = [
        'sudo bash -c "echo {} > /proc/sys/net/core/rps_sock_flow_entries"'.format(rps_sock_flow_entries)
    ]
    for i in range(num_queues):
        rps_cmds.append('sudo bash -c "echo {} > /sys/class/net/{}/queues/rx-{}/rps_flow_cnt"' \
            .format(rps_sock_flow_entries // num_queues, device, i))

    # OS param - storage
    noatime = x[0, 11] != 0
    nr_requests = str(x[0, 12])
    scheduler = schedulers[x[0, 13]]
    read_ahead_kb = str(x[0, 14])

    storage_cmds = [
        'sudo sed -i \'s/{old}/{new}/\' /etc/fstab'.format(
            old=(noatime_conf['close'] if noatime==True else noatime_conf['open']),
            new=(noatime_conf['open'] if noatime==True else noatime_conf['close'])
        ),
        'sudo bash -c "echo {} > /sys/block/{}/queue/nr_requests"'.format(nr_requests, block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/scheduler"'.format(scheduler, block_device),
        'sudo bash -c "echo {} > /sys/block/{}/queue/read_ahead_kb"'.format(read_ahead_kb, block_device),
    ]

    for cmd in storage_cmds:
        os.system(cmd)

    # workload
    wl1 = str(x[0, 15])
    wl2 = str(x[0, 16])

    
    pass

x = np.array([[0,1,2,3,4,5,6,7,8,9,10,0,101,1,768,15,16,17]])
# f_mongo(x)
return_to_default()