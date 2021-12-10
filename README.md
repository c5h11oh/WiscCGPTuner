CGPTuner.py is used to run mongo CGPTuner experiment. It will create two files : Initial_KnowledgeBase_CGPTuner.p, and KnowledgeBase_CGPTuner.p. The former store randomly generated configurations for each workload and the latter store the updated knowledge base after each iteration. That is, KnowledgeBase_CGPTuner.p will store the main result. It requires "pickle" package to open the result in python.



gpy_algorithm.py is just the initial template of CGPTuner.
