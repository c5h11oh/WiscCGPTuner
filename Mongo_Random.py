#Import Modules
#GPyOpt - Cases are important, for some reason
import GPy
import GPyOpt
from GPyOpt.methods import BayesianOptimization

#numpy
import numpy as np
from numpy.random import random_integers
import pandas as pd

from config.cgp_configs import *
import cgp

import pickle

#set random seed
np.random.seed(6666)
#define search space
domain = [{'name': 'wiredTigerCacheSizeGB', 'type': 'continuous', 'domain': (1,20)},
          {'name': 'eviction_dirty_target', 'type': 'discrete', 'domain': (5,95)},
          {'name': 'eviction_dirty_trigger', 'type': 'discrete', 'domain': (5,95)},
          {'name': 'syncdelay', 'type': 'discrete', 'domain': (10,180)},
          {'name': 'sched_latency_ns', 'type': 'discrete', 'domain': (10000,72000000)},
          {'name': 'sched_migration_cost_ns', 'type': 'discrete', 'domain': (10000,1500000)},
          {'name': 'vm.dirty_background_ratio', 'type': 'discrete', 'domain': (5,95)},
          {'name': 'vm.dirty_ratio', 'type': 'discrete', 'domain': (5,95)},
          {'name': 'vm.min_free_kbytes', 'type': 'discrete', 'domain': (10000,270000)},
          {'name': 'vm.vfs_cache_pressure', 'type': 'discrete', 'domain': (10,300)},
          {'name': 'RFS', 'type': 'discrete', 'domain': (0,1)},
          {'name': 'noatime', 'type': 'discrete', 'domain': (0,1)},
          {'name': 'nr_requests', 'type': 'discrete', 'domain': (4,20)},
          {'name': 'scheduler', 'type': 'discrete', 'domain': (0,6)},
          {'name': 'read_ahead_kb', 'type': 'discrete', 'domain': (10,384)},
          {'name': 'workload', 'type': 'discrete', 'domain': (0,2)},
          {'name': 'thread', 'type': 'discrete', 'domain': (10,20,30,40,50,60,70,80)}
         ]

# get original configuration without workload to get vender default value
original_x =  [[
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
]]


# generate random configuration
def generateRandomConfiguration(workload,nThreads):
    configuration = []
    
    #loop over each cofiguration and generate random number according to its range
    for r in domain[:15]:
        low = np.ceil(r['domain'][0])
        high = np.floor(r['domain'][1])      
        configuration.append(random_integers(low=low,high=high))
        
    configuration.append(workload)
    configuration.append(nThreads)
    
    return(np.array([configuration]))

############## start creating initial knowledge base ##############
#define workload pattern
workload_pattern = [(2,20),(2,40),(0,60),(0,80),(1,50),(1,30)]
#define cycle number of the workload pattern
number_cycles = 10
#define number of iteration at each workload pattern
number_iter_per_workload = 5
# randomly create knowledge base
KnowledgeBase = {}

number_of_KB_data_per_workload = 2
# define error penalty
penalty = { (2,20) : 1500,
            (2,40) : 1500,
            (0,60) : 3000,
            (0,80) : 4000,
            (1,50) : 2500,
            (1,30) : 1500}
for _ in range(number_cycles):
    for wp in workload_pattern:
        for _ in range(number_iter_per_workload):
            print("############################################", wp , "###################################") 
            if wp not in KnowledgeBase:
                KnowledgeBase[wp] = { 'x' : [],
                                    'y' : [],
                                    'npi' : [],
                                    'best' : np.inf,
                                    'y0' : None,
                                 'failure' : []
                                }
                new_x = np.array([original_x[0] + [wp[0],wp[1]]])
                default_value =  cgp.f_mongo(new_x)
                KnowledgeBase[wp]['y0'] = default_value[0]
            #generate random configuration
            randomConfig = generateRandomConfiguration(wp[0],wp[1])
            # run random configuration
            objectiveValue = cgp.f_mongo(randomConfig)
            
            # flag if error happens
            if objectiveValue[0] < 0:
                KnowledgeBase[wp]['failure'].append(1)
                KnowledgeBase[wp]['x'].append(list(randomConfig[0]))
                KnowledgeBase[wp]['y'].append([penalty[wp]])
            else:
                KnowledgeBase[wp]['failure'].append(0)
                if objectiveValue[0] < KnowledgeBase[wp]['best']:
                    KnowledgeBase[wp]['best'] =  objectiveValue[0]

                # add to knowledge base
                KnowledgeBase[wp]['x'].append(list(randomConfig[0]))
                KnowledgeBase[wp]['y'].append([objectiveValue[0]])


        #KnowledgeBase[(wl,numT)]['best'] = min(KnowledgeBase[(wl,numT)]['y'])[0]
        KnowledgeBase[wp]['npi'] = ((KnowledgeBase[wp]['y0'] - np.array(KnowledgeBase[wp]['y']))\
                                              / (KnowledgeBase[wp]['y0'] - KnowledgeBase[wp]['best'])).tolist()


        with open('KnowledgeBase_Random.p', 'wb') as fp:
            pickle.dump(KnowledgeBase, fp)
