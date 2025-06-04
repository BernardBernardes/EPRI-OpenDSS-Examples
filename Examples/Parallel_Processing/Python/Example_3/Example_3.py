
# coding: utf-8

'''

This example shows how to compile and solve different circuits using the parallel processing suite.

'''
# In[1]:


import win32com.client
import time

DSSObj = win32com.client.dynamic.Dispatch("OpenDSSEngine.DSS")
DSSText = DSSObj.Text
DSSCircuit = DSSObj.ActiveCircuit
DSSSolution = DSSCircuit.Solution
DSSParallel = DSSCircuit.Parallel
DSSBus=DSSCircuit.ActiveBus
DSSCtrlQueue=DSSCircuit.CtrlQueue
DSSObj.Start(0)
NCPUs=DSSParallel.NumCPUs
print(' total number of NCPUs', NCPUs )

DSSText.Command='ClearAll'
DSSText.Command='set parallel=No'

Ckt_List = ['C:/Program Files/OpenDSS/EPRITestCircuits/ckt5/master_ckt5.DSS',
            'C:/Program Files/OpenDSS/EPRITestCircuits/ckt7/Master_ckt7.DSS',
            'C:/Program Files/OpenDSS/EPRITestCircuits/ckt24/master_ckt24']

EndArray=[] # for checking when all the actors are done
yDelta=8760/(NCPUs-1)
ActorCPU =[]

x = 0

for Ckt in Ckt_List:
    print('Core Number',x)
    if x != 0:
        DSSParallel.CreateActor()
    DSSText.Command='compile "' + Ckt + '"'
    DSSText.Command='Solve'

    DSSText.Command='set mode=yearly totaltime=0 number=4000 hour=0'
    EndArray.append(1)
    x += 1
            
DSSText.Command='set parallel=Yes'
DSSText.Command='SolveAll'
DSSText.Command='Wait'
BoolStatus = False
time.sleep(1);
while BoolStatus == False:
    ActorStatus = list(DSSParallel.ActorStatus);
    BoolStatus = ActorStatus == EndArray
    ActorProgress=DSSParallel.ActorProgress
    print('BoolStatus = ',BoolStatus,' ActorStatus = ',ActorStatus,' ActorProgress = ', ActorProgress)
    i = 1
    for Ckt in Ckt_List:
        DSSParallel.ActiveActor = i;
        CHour = DSSSolution.dblHour;
        print('Actor Time(hours)',CHour);
        i += 1
    time.sleep(0.5)
    
print('Simulation finished');

