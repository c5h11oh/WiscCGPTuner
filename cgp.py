# Utilities
import os, time
import shlex
import glob
import re
import math
from ruamel.yaml import YAML
import numpy as np
# Configurations
from config.cgp_configs import *


def send_cmd(cmd, background=False):
    ssh_cmd = 'ssh {} {}'.format(database, shlex.quote(cmd))
    if (background):
        ssh_cmd += ' &'
    print(ssh_cmd)
    os.system(ssh_cmd)
    # os.system(cmd)


def mongo_setup_system_params(x):
    # OS param - kernel, vm
    sched_latency_ns = int(x[0, 4])
    sched_migration_cost_ns = int(x[0, 5])
    dirty_background_ratio = int(x[0, 6])
    dirty_ratio = int(x[0, 7])
    min_free_kbytes = int(x[0, 8])
    vfs_cache_pressure = int(x[0, 9])
    
    print('sanity check : ', sched_latency_ns)
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
    RFS = bool(int(x[0, 10]))
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
    nr_requests = 2 ** int(x[0, 12])
    scheduler = storage_schedulers[int(x[0, 13])]
    read_ahead_kb = int(x[0, 14])

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


def mongo_return_to_default():
    mongo_setup_system_params(mongo_default_x)


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

    # mount storage at /db
    mount_cmd = 'sudo mount -o defaults' + (',noatime' if bool(int(x[0, 11])) else '') + f' /dev/{block_device} /db'
    send_cmd(mount_cmd)

    # setup system params (OS, network, storage)
    mongo_setup_system_params(x)

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
    wl_mix = chr(ord('a') + int(x[0, 15])) # [0, 1, 2] => ['a', 'b', 'c']
    wl_thd = int(x[0, 16])
    ycsb_load_cmd = f'{ycsb_path}/bin/ycsb load mongodb -threads {db_cpu} -s -P {ycsb_path}/workloads/workload{wl_mix}'
    for k, v in ycsb_params.items():
        ycsb_load_cmd += f' -p {k}={v}'
    send_cmd(ycsb_load_cmd)

    # run YCSB (from this server 'ycsb')
    ycsb_run_cmd = f'{ycsb_path}/bin/ycsb run mongodb -threads {wl_thd} -P {ycsb_path}/workloads/workload{wl_mix} -p mongodb.url=mongodb://{database}:27017/ycsb'
    for k, v in ycsb_params.items():
        ycsb_run_cmd += f' -p {k}={v}'
    ycsb_run_cmd += ' > ycsb_result'
    os.system(ycsb_run_cmd)
    with open('ycsb_result', 'r') as f:
        result = f.read()

        # latency
        m = re.search('\[UPDATE\], AverageLatency\(us\), (NaN|\d+\.\d+)', result)
        update_latency = float(m.group(1)) if m else math.nan
        m = re.search('\[READ\], AverageLatency\(us\), (NaN|\d+\.\d+)', result)
        read_latency = float(m.group(1)) if m else math.nan
        if math.isnan(update_latency) or math.isnan(read_latency):
            latency = read_latency if math.isnan(update_latency) else update_latency
        else:
            latency = (update_latency + read_latency) /  2

        # handling failure
        m = re.search('\[.+-FAILED\]', result)
        if m is not None:
            latency = -1

    # stop MongoDB
    send_cmd('pkill mongod')

    # unmount /db
    send_cmd(f'sudo umount /dev/{block_device}')

    # reset params (optional)
    mongo_return_to_default()

    return np.array([latency])


def cass_setup_system_params(x):
    send_cmd(f'cp default.cassandra.yaml cassandra.yaml')
    if (x[0][0] != -1):
        send_cmd(f'yq e -i ".commitlog_compression[0].class_name = {x[0][0]}" cassandra.yaml')
    send_cmd(f'yq e -i ".commitlog_segment_size_in_mb = {x[0][1]}" cassandra.yaml')
    send_cmd(f'yq e -i ".commitlog_sync_period_in_ms = {x[0][2]}" cassandra.yaml')
    send_cmd(f'yq e -i ".compaction_throughput_mb_per_sec = {x[0][4]}" cassandra.yaml')
    if (x[0][5] != -1):
        send_cmd(f'yq e -i ".concurrent_compactors = {x[0][5]}" cassandra.yaml')
    send_cmd(f'yq e -i ".concurrent_reads = {x[0][6]}" cassandra.yaml')
    send_cmd(f'yq e -i ".concurrent_writes = {x[0][7]}" cassandra.yaml')
    if (x[0][8] != -1):
        send_cmd(f'yq e -i ".file_cache_size_in_mb = {x[0][8]}" cassandra.yaml')
    send_cmd(f'cp cassandra.yaml /etc/cassandra/cassandra.yaml')

    # JVM
    if (CONFIGURE_JVM):
        os.system(f'scp {database}:/etc/cassandra/jvm.options.backup-20211208 config/jvm.options')
        jvm_sed_cmds = [
            f"s/(CMSInitiatingOccupancyFraction=)[0-9]*/\\1{x[0][9]}/",
            f"s/(MaxTenuringThreshold=)[0-9]*/\\1{x[0][13]}/",
            f"s/(SurvivorRatio=)[0-9]*/\\1{x[0][16]}/",
        ]
        if (x[0][10] != -1):
            jvm_sed_cmds.append(f"s/#(-XX:ConcGCThreads=)[0-9]*/\\1{x[0][10]}/")
        if (x[0][11] == 1):
            jvm_sed_cmds.append(f"s/-XX:\\+UseParNewGC//")
            jvm_sed_cmds.append(f"s/-XX:\\+UseConcMarkSweepGC/-XX:\\+UseG1GC/")
        if (x[0][12] != -1):
            jvm_sed_cmds.append(f"s/#-Xms4G/-Xms{x[0][12]}G/")
            jvm_sed_cmds.append(f"s/#-Xmx4G/-Xmx{x[0][12]}G/")
        if (x[0][15] != -1):
            jvm_sed_cmds.append(f"s/#(-XX:ParallelGCThreads=)[0-9]*/\\1{x[0][15]}/")
        jvm_sed_cmd = 'sed -i -r '
        for cmd in jvm_sed_cmds:
            jvm_sed_cmd += f"-e '{cmd}' "
        jvm_sed_cmd += 'config/jvm.options'
        os.system(jvm_sed_cmd)

        if (x[0][14] != -1):
            os.system(f'echo "-XX:NewRatio={x[0][14]}" >>config/jvm.options')
        os.system(f'scp config/jvm.options {database}:/etc/cassandra/')

    # OS
    if (CONFIGURE_OS):
        pass
        # TODO OS

def cass_return_to_default():
    # Cassandra and JVM: simply place back backup cassandra.yaml and jvm.options
    send_cmd('cp /etc/cassandra/cassandra.yaml.backup-20211208 /etc/cassandra/cassandra.yaml')
    send_cmd('cp /etc/cassandra/jvm.options.backup-20211208 /etc/cassandra/jvm.options')
    
    # OS:
    # TODO OS


def f_cassandra(x):
    """
    input: configuration + workload x
    output: mean response time R (ms)
    """
    # sanity check
    ## Cassandra
    if (x[0][0] < -1 or x[0][0] > 2): raise ValueError('commitlog_compression')
    if (x[0][1] < 8 or x[0][1] > 64 or (x[0][1] % 8 != 0)): raise ValueError('commitlog_segment_size_in_mb')
    if (x[0][2] < 5000 or x[0][2] > 50000): raise ValueError('commitlog_sync_period_in_ms')
    if (x[0][3] < 0 or x[0][3] > 2): raise ValueError('compact_stratrgy')
    if (x[0][4] < 0 or x[0][4] > 128 or (x[0][4] % 16 != 0)): raise ValueError('compaction_throughput_mb_per_sec')
    if (x[0][5] != -1 and (x[0][5] < 2 or x[0][5] > 8)): raise ValueError('concurrent_compactors')
    if (x[0][6] < 16 or x[0][6] > 128 or (x[0][6] % 16 != 0)): raise ValueError('concurrent_reads')
    if (x[0][7] < 16 or x[0][7] > 128 or (x[0][7] % 16 != 0)): raise ValueError('concurrent_reads')
    if (x[0][8] != -1 and (x[0][8] < 32 or x[0][8] > 1024 or (x[0][8] % 32 != 0))): raise ValueError('file_cache_size_in_mb')
    
    if (CONFIGURE_JVM):
        ## JVM
        if (x[0][9] < 50 or x[0][9] > 99): raise ValueError('CMSInitiatingOccupancyFraction')
        if (x[0][10] != -1 and (x[0][10] < 1 or x[0][10] > 64)): raise ValueError('ConcGCThreads')
        if (x[0][11] < 0 or x[0][11] > 1): raise ValueError('GC_Type')
        if (x[0][12] != -1 and (x[0][12] < 1 or x[0][12] > 24)): raise ValueError('Xmx_Xms')
        if (x[0][13] < 0 or x[0][13] > 15): raise ValueError('MaxTenuringThreshold')
        if (x[0][14] != -1 and (x[0][14] < 1 or x[0][14] > 4)): raise ValueError('NewRatio')
        if (x[0][15] != -1 and (x[0][15] < 1 or x[0][15] > 64)): raise ValueError('ParallelGCThreads')
        if (x[0][16] < 4 or x[0][16] > 32): raise ValueError('SurvivorRatio')
    
    if (CONFIGURE_OS):
        # TODO: OS
        pass

    # mount storage at /db
    mount_cmd = f'sudo mount -o defaults /dev/{block_device} /db'
    send_cmd(mount_cmd)

    # setup system params (Cassandra, JVM, OS)
    cass_setup_system_params(x)

    # init Cassandra with params
    send_cmd('sudo systemctl stop cassandra.service')
    send_cmd('sudo systemctl start cassandra.service')
    # with "ALTER TABLE ycsb.usertable WITH compaction = {\'class\': \'{cmp}\'}".format(cmp=x[0][3]) as sql_stmt:
    sql_stmt = "ALTER TABLE ycsb.usertable WITH compaction = {\'class\': \'" + cass_compact_strategy[x[0][3]] + "\'}"
    send_cmd(f'cqlsh -e "{sql_stmt}"')

    # drop previous data if exists
    # TODO: copy raw data as Konstantinos said?
    send_cmd('cqlsh -e "TRUNCATE ycsb.usertable;"')

    # load workload (on server 'database')
    # TODO: copy raw data as Konstantinos said?
    wl_mix = chr(ord('a') + int(x[0][23])) # [0, 1, 2] => ['a', 'b', 'c']
    wl_thd = int(x[0][24])
    ycsb_load_cmd = f'{ycsb_path}/bin/ycsb load cassandra-cql -threads {db_cpu} -s -P {ycsb_path}/workloads/workload{wl_mix} -p hosts=127.0.0.1'
    for k, v in ycsb_params.items():
        ycsb_load_cmd += f' -p {k}={v}'
    send_cmd(ycsb_load_cmd)

    # run YCSB (from this server 'ycsb')
    ycsb_run_cmd = f'{ycsb_path}/bin/ycsb run cassandra-cql -threads {wl_thd} -P {ycsb_path}/workloads/workload{wl_mix} -p hosts={database}'
    for k, v in ycsb_params.items():
        ycsb_run_cmd += f' -p {k}={v}'
    ycsb_run_cmd += ' > ycsb_result'
    os.system(ycsb_run_cmd)
    with open('ycsb_result', 'r') as f:
        result = f.read()
        # latency
        m = re.search('\[UPDATE\], AverageLatency\(us\), (NaN|\d+\.\d+)', result)
        update_latency = float(m.group(1)) if m else math.nan
        m = re.search('\[READ\], AverageLatency\(us\), (NaN|\d+\.\d+)', result)
        read_latency = float(m.group(1)) if m else math.nan
        if math.isnan(update_latency) or math.isnan(read_latency):
            latency = read_latency if math.isnan(update_latency) else update_latency
        else:
            latency = (update_latency + read_latency) /  2

        # handling failure
        m = re.search('\[.+-FAILED\]', result)
        if m is not None:
            latency = -1

    # stop Cassandra
    send_cmd('sudo systemctl stop cassandra.service')

    # unmount /db
    send_cmd(f'sudo umount /dev/{block_device}')

    # reset params (optional)
    cass_return_to_default()

    return np.array([latency])


if __name__ == '__main__':
    test_cassandra = [[
        # Cassandra param (start from 0)
        1,
        16,
        5000,
        1,
        0,
        3,
        64,
        80,
        cass_default['file_cache_size_in_mb'],

        # JVM param (start from 9)
        80,
        20,
        1,
        23,
        13,
        2,
        17,
        7, 

        # OS param (start from 17)
        cass_default['CPUSchedNrMigrate'],
        cass_default['MemoryTransparentHugepageEnabled'],
        cass_default['MemoryVmDirtyExpire'],
        cass_default['NetworkNetIpv4TcpMaxSynBacklog'],
        cass_default['scheduler'],
        cass_default['read_ahead_kb'],

        # workload (start from 23)
        0,
        db_cpu
    ]]
    f_cassandra(test_cassandra)
    # cass_setup_system_params(test_cassandra)
    # cass_return_to_default()
    
    # test_mongo = np.array([[      11,       83,       37,        1, 46432792,  1467552,
    #                         72,        5,   100868,      205,        0,        1,
    #                     22333,        2,      314,        2,       40]])

    # latency = f_mongo(test_mongo)
    # latency = f_mongo(mongo_default_x)
    # print(f'latency = {latency}')
    # return_to_default()
