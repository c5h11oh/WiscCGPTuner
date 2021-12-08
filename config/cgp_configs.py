import numpy as np

# ycsb
ycsb_params = {
    'recordcount': 60000, # number of records. appx to DB size in KB. paper uses 30 000 000.
    'operationcount': 2147483647,
    'maxexecutiontime': 10, # in seconds
}
## ycsb path
ycsb_path = '/home/cgptuner/ycsb-0.17.0'


# database server
## hostname
database="database"
db_cpu = 8 # cpu count of the database server 

## configurations
storage_schedulers = ['bfq', 'kyber', 'none', 'mq-deadline', 'deadline', 'cfq', 'noop' ]
block_device='sdb' # /db resides in /dev/{block_device}
network_device = 'ens4'

## mongo configurations
mongo_dir = '/db/mongodb' # where db_path and log_path reside
mongo_default = { # database server default configurations
    # OS
    'sched_latency_ns' : 24000000,
    'sched_migration_cost_ns' : 500000,
    'dirty_background_ratio' : 10,
    'dirty_ratio' : 20,
    'min_free_kbytes' : 67584,
    'vfs_cache_pressure' : 100,
    # RFS 
    'RFS': 0,
    # Storage
    'noatime' : False,
    'nr_requests' : 256,
    'scheduler' : 3, # in range [0, sizeof(schedulers)]
    'read_ahead_kb' : 128,
}
mongo_default_x = np.array([[
    # DB param
    0,
    0,
    0,
    0,
    # OS param - kernel, vm
    mongo_default['sched_latency_ns'],
    mongo_default['sched_migration_cost_ns'],
    mongo_default['dirty_background_ratio'],
    mongo_default['dirty_ratio'],
    mongo_default['min_free_kbytes'],
    mongo_default['vfs_cache_pressure'],
    # OS param - network
    0, # RFS
    # OS param - storage
    mongo_default['noatime'],
    mongo_default['nr_requests'],
    mongo_default['scheduler'],
    mongo_default['read_ahead_kb'],
    # workload
    0,
    db_cpu,
]])

## cassandra configurations
cass_compression = ['LZ4Compressor', 'SnappyCompressor', 'DeflateCompressor']
cass_compact_strategy = ['SizeTieredCompactionStrategy', 'LeveledCompactionStrategy', 'TimeWindowCompactionStrategy']
cass_default = { # comments are their domains. -1 means 'commented out'
    # Cassandra param
    ## cassandra.yaml
    'commitlog_compression': 0, # [-1..2] discrete.
    'commitlog_segment_size_in_mb': 32, # 8, 16, 32 (, 48, 64)
    'commitlog_sync_period_in_ms': 10000, # dunno... [5000..50000] ?

    ## ALTER TABLE tcsb WITH compaction =
    ##   {'class' : 'SizeTieredCompactionStrategy'}
    'compact_stratrgy' : 0, # [0..2] discrete

    ## cassandra.yaml
    'compaction_throughput_mb_per_sec': 64, # 0 (disable throttling), [k*16], k = [0..8]
    'concurrent_compactors': -1, # -1, [2..8]
    'concurrent_reads': 32, # [k*16], k = [1..8]
    'concurrent_writes': 32, # [k*16], k = [1..8]
    'file_cache_size_in_mb': 512, # [k*32], k = [1..32]

    # JVM param
    ## /etc/cassandra/jvm.options
    'CMSInitiatingOccupancyFraction': 75,
    'ConcGCThreads': -1,
    'GC_Type': 0, 
    'Xmx_Xms': -1, # -1, [1G..max RAM size-8G?] => -1, [1..24]
    'MaxTenuringThreshold': 1, # [0..15]
    'NewRatio': -1, # -1, [1..4]
    'ParallelGCThreads': -1, # -1, [1..64?]
    'SurvivorRatio': 8, # [4..32]

    # OS param not working on it yet
    'CPUSchedNrMigrate': -1,
    'MemoryTransparentHugepageEnabled': -1,
    'MemoryVmDirtyExpire': -1,
    'NetworkNetIpv4TcpMaxSynBacklog': -1,
    'scheduler': 3,
    'read_ahead_kb': 128,
}
cass_default_x = np.array([[
    # Cassandra param (start from 0)
    cass_default['commitlog_compression'],
    cass_default['commitlog_segment_size_in_mb'],
    cass_default['commitlog_sync_period_in_ms'],
    cass_default['compact_stratrgy'],
    cass_default['compaction_throughput_mb_per_sec'],
    cass_default['concurrent_compactors'],
    cass_default['concurrent_reads'],
    cass_default['concurrent_writes'],
    cass_default['file_cache_size_in_mb'],

    # JVM param (start from 9)
    cass_default['CMSInitiatingOccupancyFraction'],
    cass_default['ConcGCThreads'],
    cass_default['GC_Type'],
    cass_default['Xmx_Xms'],
    cass_default['MaxTenuringThreshold'],
    cass_default['NewRatio'],
    cass_default['ParallelGCThreads'],
    cass_default['SurvivorRatio'],

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
]])

# obsolete
"""
noatime_conf = {
    'close': 'defaults\t0 2', 
    'open': 'defaults,noatime\t0 2', 
}
"""