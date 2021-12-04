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



#define search space
domain = [{'name': 'wiredTigerCacheSizeGB', 'type': 'continuous', 'domain': (0,20)},
          {'name': 'eviction_dirty_target', 'type': 'discrete', 'domain': (0,99)},
          {'name': 'eviction_dirty_trigger', 'type': 'discrete', 'domain': (0,99)},
          {'name': 'syncdelay', 'type': 'discrete', 'domain': (0,180)},
          {'name': 'sched_latency_ns', 'type': 'discrete', 'domain': (0,72000000)},
          {'name': 'sched_migration_cost_ns', 'type': 'discrete', 'domain': (0,1500000)},
          {'name': 'vm.dirty_background_ratio', 'type': 'discrete', 'domain': (0,99)},
          {'name': 'vm.dirty_ratio', 'type': 'discrete', 'domain': (0,99)},
          {'name': 'vm.min_free_kbytes', 'type': 'discrete', 'domain': (0,270000)},
          {'name': 'vm.vfs_cache_pressure', 'type': 'discrete', 'domain': (0,300)},
          {'name': 'RFS', 'type': 'discrete', 'domain': (0,1)},
          {'name': 'noatime', 'type': 'discrete', 'domain': (0,1)},
          {'name': 'nr_requests', 'type': 'discrete', 'domain': (0,24000)},
          {'name': 'scheduler', 'type': 'discrete', 'domain': (0,6)},
          {'name': 'read_ahead_kb', 'type': 'discrete', 'domain': (0,384)},
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
]]

#example function 
### important: the function output value should be in the form of np.array([value])
def f_mongo(x):
    out = 0
    for i in x[0]:
        out += i
    return(np.array([out]))

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
            KBX += KB[workPattern]['x']
            KBY += KB[workPattern]['npi']
    else :
        for workPattern in KnowledgeBase:
            KBX += KB[workPattern]['x']
            KBY += KB[workPattern]['y']
            
    return KBX, KBY
    

############## start creating initial knowledge base ##############
KnowledgeBase = {}
# randomly create knowledge base
number_of_KB_data_per_workload = 3

workload = [0,1,2]

nThreads = [10,20,30,40,50,60,70,80]

print('creating prior knowledge base')
for wl in workload:
    for numT in nThreads:
        for _ in range(number_of_KB_data_per_workload):
            
            if (wl,numT) not in KnowledgeBase:
                KnowledgeBase[(wl,numT)] = { 'x' : [],
                                  'y' : [],
                                  'npi' : [],
                                  'best' : np.inf,
                                  'y0' : None
                                }
                new_x = np.array([original_x[0] + [wl,numT]])
                default_value =  f_mongo(new_x)
                KnowledgeBase[(wl,numT)]['y0'] = default_value[0]
            #generate random configuration
            randomConfig = generateRandomConfiguration(wl,numT)
            
            # run random configuration
            objectiveValue = f_mongo(randomConfig)
            
            # add to knowledge base
            KnowledgeBase[(wl,numT)]['x'].append(list(randomConfig[0]))
            KnowledgeBase[(wl,numT)]['y'].append([objectiveValue[0]])
        KnowledgeBase[(wl,numT)]['best'] = min(KnowledgeBase[(wl,numT)]['y'])[0]
        KnowledgeBase[(wl,numT)]['npi'] = ((KnowledgeBase[(wl,numT)]['y0'] - np.array(KnowledgeBase[(wl,numT)]['y']))\
                                          / (KnowledgeBase[(wl,numT)]['y0'] - KnowledgeBase[(wl,numT)]['best'])).tolist()
#print(KnowledgeBase)
############## stop creating initial knowledge base ##############

############ define CGP kernel ############
#construct new kernel
kernel1 = GPy.kern.sde_Matern52(input_dim=15, variance=1., lengthscale=1., active_dims=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14])
kernel2 = GPy.kern.sde_Matern52(input_dim=2, variance=1., lengthscale=1., active_dims=[15,16])
kernel = kernel1 * kernel2


############ start CGP algorithmn ############
#define workload pattern
workload_pattern = [(2,20),(2,40),(0,60),(0,80),(1,50),(1,30)]
#define cycle number of the workload pattern
number_cycles = 5
#define number of iteration at each workload pattern
number_iter_per_workload = 5

for _ in range(number_cycles):
    for wp in workload_pattern:
        for _ in range(number_iter_per_workload):
            print('working on workload : ', wp)
            #detected work load cand fix the workload
            context = {'workload': wp[0], 'thread': wp[1]} # this will be used to fix the workload
            
            #get initial data
            KBX, KBY = NPI(KB=KnowledgeBase,toNPI = False)

            CGPTuner = BayesianOptimization(f=f_mongo,initial_design_numdata=0, 
                                            domain=domain,
                                            kernel=kernel,
                                            X=np.array(KBX),
                                            Y=np.array(KBY),
                                            acquisition_type='LCB')
            
            #fix workload and get the next configuration
            new_point = CGPTuner.suggest_next_locations(context=context)

            #add the result to the knowledge base
            KnowledgeBase[wp]['x'].append(list(new_point[0]))
            KnowledgeBase[wp]['y'].append([f_mongo(new_point)[0]])
            
            #update NPI for that workload
            KnowledgeBase[wp]['best'] = min(KnowledgeBase[wp]['y'])[0]
            KnowledgeBase[wp]['npi'] = ((KnowledgeBase[wp]['y0'] - np.array(KnowledgeBase[wp]['y']))\
                                          / (KnowledgeBase[wp]['y0'] - KnowledgeBase[wp]['best'])).tolist()

print(KnowledgeBase)