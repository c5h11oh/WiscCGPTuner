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

#get data from knowledge base
def NPI(KB,toNPI = True):
    KBX = []
    KBY = []
            
    if toNPI == True:
        for workPattern in KB:
            for i in range(len(KB[workPattern]['x'])):
                if KB[workPattern]['y'][i][0] > 0:
                    KBX.append(KB[workPattern]['x'][i])
                    KBY.append(KB[workPattern]['npi'][i])
    else :
        for workPattern in KnowledgeBase:
            for i in range(len(KB[workPattern]['x'])):
                if KB[workPattern]['y'][i][0] > 0:
                    KBX.append(KB[workPattern]['x'][i])
                    KBY.append(KB[workPattern]['y'][i])
    return KBX, KBY
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
'''
print('creating prior knowledge base')
for wp in workload_pattern:
    for _ in range(number_of_KB_data_per_workload):
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


    with open('Initial_KnowledgeBase_CGPTuner.p', 'wb') as fp:
        pickle.dump(KnowledgeBase, fp)
'''

with open('Initial_KnowledgeBase_CGPTuner.p', 'rb') as fp:
    KnowledgeBase = pickle.load(fp)


############## stop creating initial knowledge base ##############

############ define CGP kernel ############
#construct new kernel
kernel1 = GPy.kern.sde_Matern52(input_dim=15, variance=1., lengthscale=1., active_dims=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14])
kernel2 = GPy.kern.sde_Matern52(input_dim=2, variance=1., lengthscale=1., active_dims=[15,16])
kernel = kernel1 * kernel2


############ start CGP algorithmn ############

for cycle in range(number_cycles):
    print('###################################### cycle : ', cycle)
    for wp in workload_pattern:
        for _ in range(number_iter_per_workload):
            print('##########################################working on workload : ', wp)
            #detected work load cand fix the workload
            context = {'workload': wp[0], 'thread': wp[1]} # this will be used to fix the workload
            
            #get initial data
            KBX, KBY = NPI(KB=KnowledgeBase,toNPI = False)

            CGPTuner = BayesianOptimization(f=cgp.f_mongo,initial_design_numdata=0, 
                                            domain=domain,
                                            kernel=kernel,
                                            X=np.array(KBX),
                                            Y=np.array(KBY),
                                            acquisition_type='LCB')
            
            #fix workload and get the next configuration
            next_point = CGPTuner.suggest_next_locations(context=context)
            
            new_point = []
            for i in next_point[0]:
                new_point.append(int(i))
            
            
            new_point = np.array([new_point])
            print(new_point)
            #add the result to the knowledge base
            objectiveValue = cgp.f_mongo(new_point)
            
            # flag if error happens
            if objectiveValue[0] < 0:
                KnowledgeBase[wp]['failure'].append(1)
                KnowledgeBase[wp]['x'].append(list(new_point[0]))
                KnowledgeBase[wp]['y'].append([penalty[wp]])
            else:
                KnowledgeBase[wp]['failure'].append(0)
                if objectiveValue[0] < KnowledgeBase[wp]['best']:
                     KnowledgeBase[wp]['best'] =  objectiveValue[0]
            
                KnowledgeBase[wp]['x'].append(list(new_point[0]))
                KnowledgeBase[wp]['y'].append([objectiveValue[0]])
            
            #update NPI for that workload
            KnowledgeBase[wp]['best'] = min(KnowledgeBase[wp]['y'])[0]
            KnowledgeBase[wp]['npi'] = ((KnowledgeBase[wp]['y0'] - np.array(KnowledgeBase[wp]['y']))\
                                          / (KnowledgeBase[wp]['y0'] - KnowledgeBase[wp]['best'])).tolist()

            with open('KnowledgeBase_CGPTuner.p', 'wb') as fp:
                pickle.dump(KnowledgeBase, fp)
