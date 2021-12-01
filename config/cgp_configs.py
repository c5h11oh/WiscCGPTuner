# OS param default values on GCP
    # kernel.sched_latency_ns = 24000000
    # kernel.sched_migration_cost_ns = 500000
    # vm.dirty_background_ratio = 10
    # vm.dirty_ratio = 20
    # vm.min_free_kbytes = 67584
    # vm.vfs_cache_pressure = 100
    
    # noatime
    # nr_requests = 8192
    # scheduler = [none] mq-deadline
    # read_ahead_kb = 128
default = {
    'sched_latency_ns' : 24000000,
    'sched_migration_cost_ns' : 500000,
    'dirty_background_ratio' : 10,
    'dirty_ratio' : 20,
    'min_free_kbytes' : 67584,
    'vfs_cache_pressure' : 100,

    'noatime' : False,
    'nr_requests' : 8192,
    'scheduler' : 3,
    'read_ahead_kb' : 128,
}
mongo_dir = '/home/cgptuner/mongodb'
block_device='sda'
schedulers = ['bfq', 'kyber', 'none', 'mq-deadline', 'deadline', 'cfq', 'noop' ]
noatime_conf = {
    'close': 'defaults\t0 1', 
    'open': 'defaults,noatime\t0 1', 
}