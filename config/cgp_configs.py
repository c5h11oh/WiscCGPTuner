# experiment
ycsb_params = {
    'recordcount': 60000, # number of records. appx to DB size in KB. paper uses 30 000 000.
    'operationcount': 2147483647,
    'maxexecutiontime': 10, # in seconds
}

# database server
## hostname
database="database"
db_cpu = 8 # cpu count of the database server 

## ycsb
ycsb_path = '/home/cgptuner/ycsb-0.17.0'

## configurations
default = { # database server default configurations
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
block_device='sdb' # /db resides in /dev/{block_device}
mongo_dir = '/db/mongodb' # where db_path and log_path reside
schedulers = ['bfq', 'kyber', 'none', 'mq-deadline', 'deadline', 'cfq', 'noop' ] # storage schedulers
network_device = 'ens4'


# obsolete
"""
noatime_conf = {
    'close': 'defaults\t0 2', 
    'open': 'defaults,noatime\t0 2', 
}
"""