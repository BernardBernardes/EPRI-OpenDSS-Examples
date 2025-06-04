# -*- coding: utf-8 -*-
"""
Created on Thu Jan  20 10:23:05 2025

@author: Davis Montenegro

Implements a constant PQ load using the pyControl object structure within an
OpenDSS simulation. Use this structure as base for implementing your own
controls.
 
"""

import cmath, math
import json
import numpy as np
import traceback

# Connects to DSS through the PIPE
thismodelname = 'loads48_py'

parsRdy = False

if "pars" in locals():
    parsRdy = True


#%%
'''
Some subroutines
'''

DSSQry = '? Load.' 

'''
Routine for parsing a DSS String into array of strings
'''
 
def Str2StrArray(myString):
    myResult = myString.replace('[','').replace(']','').split(',')
    return myResult

'''
Routine for converting a complex to str
''' 
def Cmplx2Str(myCNum):
    Token   = ''
    if myCNum.imag >= 0:
        Token = '+'
    Result = "{:.5f}{}{:.5f}j".format(myCNum.real, Token, myCNum.imag)
    
    return Result

'''
Routine for converting an array of complex to an array of string
''' 
def CmplxArr2Str(myArray):
    Result  = []
    for mycell in myArray:
        Token   = ''
        if mycell.imag >= 0:
            Token = '+'
        Cval = "{:.5f}{}{:.5f}j".format(mycell.real, Token, mycell.imag)
        Result.append(Cval)
    
    return Result

'''
Routine for converting a string to an array of complex
''' 
def Str2CmplxArr(myStr):
    Result  = []
    for mycell in myStr:
        if (mycell != ''):
            Result = np.append(Result, complex(mycell))
    
    return Result

'''
Routine for converting a string to a complex matrix (Y prim)
''' 
def Str2CmplxMat(myStr):
    myStr = myStr.replace('[','').replace(']','')                       # Remove wrapper
    ArrStr = myStr.split('|')                                           # Get the matrix size
    MSize = len(ArrStr)
    Result = np.zeros(MSize**2, dtype=complex).reshape(MSize,MSize)     # Initialize the matrix
    nrow = 0
    ncol = 0
    for StrRow in ArrStr:                                               # Populate
        ArrRow = StrRow.split(' ')
        for mycell in ArrRow:
            if mycell != '':
                Result[nrow][ncol] = complex(mycell)
                if nrow != ncol:
                    Result[ncol][nrow] = complex(mycell)
                ncol += 1
        nrow += 1
        ncol = 0
    
    return Result



#%%
'''
Here we check if the script is executed for he first time, if so, initilizes 
DSS and the local variables required. Otherwise, brings back the values
from DSS memory to keep iterating
'''
if not parsRdy:
    # These are the model parameters and variables for the process
    pars = {
        'bus'       : '',                           # The name of the bus to measure (Voltage)
        'Last_V'    : ['0+0j', '0+0j', '0+0j'],     # Stores the last voltage read from the simulation
        'Load_Name' :'s48',                         # The name of the Load to control
        'Load_PQ'   : '80e3+30e3j',                 # This is the power we want for the load (P + jQ)
        'kV_rating' : 0.0,                          # The load kV rating
        'Yprim'     : '',                           # THe Yprimitive for this model
        'NumCond'   : 4,                            # Number of conductors for the model
        'NumPhases' : 3,                            # Number of phases for the model
        'iteration' : 0                             # Stores the number of iterations used by this model
        }
    # Since this is the first time, get values from DSS and save them locally
    # 1. Save the bus name
    DSSText.Command = DSSQry + pars['Load_Name'] + '.bus1'
    myBuses = Str2StrArray(DSSText.Result)
    pars['bus'] = myBuses[0].split('.')[0].replace(' ','')            # Stores the bus name

    # 2. Calculate and set the Y primitive
    DSSText.Command = DSSQry + pars['Load_Name'] + '.kV'
    pars['kV_rating'] = (float((DSSText.Result).replace(' ','')) * 1e3) / math.sqrt(3) # LN voltage

    # This is a wye connected load, then Yeq is:
    Yeq = (np.conjugate(complex(pars['Load_PQ']))/pars['NumPhases'])/(pars['kV_rating']**2)

    Yprim = np.zeros(pars['NumCond']**2, dtype=complex).reshape(pars['NumCond'],pars['NumCond'])
    for i in range(pars['NumPhases']):
        Yprim[i][i] = Yeq
        Yprim[i][pars['NumPhases']] = -1 * Yeq
        Yprim[pars['NumPhases']][i] = -1 * Yeq
    Yprim[pars['NumPhases']][pars['NumPhases']] = Yeq * pars['NumPhases']

    # Now send the Yprim to OpenDSS in the right format
    DSSYCmd = '['
    for i in range(pars['NumCond']):
        for j in range(i + 1):
            DSSYCmd += Cmplx2Str(Yprim[i][j]) + ' '
        if i < pars['NumPhases']:
            DSSYCmd += '| '
    DSSYCmd += ']'
    DSSText.Command = 'select Load.' + pars['Load_Name']
    DSSText.Command = 'set Yprim=' + DSSYCmd
    
    pars['Yprim'] = Yprim
    
    print('Model initialized')
        
else:
    print('The model was already initialized ')

#%%
'''
The Load model starts here
'''  
DSSSolve = 'no'
try:
    
    idx = 0 
    Converged = False     

    idx += 1
    # First, get the voltage at this bus
    DSSText.Command = 'set Bus=' + pars['bus']
    DSSText.Command = 'voltages'
    VperPhase = DSSText.Result.replace(' ','').split(',')
    j = 0
    cVolts = []
    for i in range(pars['NumPhases']):
        cValues = np.array(cmath.rect(float(VperPhase[j].replace(' ','')), float(VperPhase[j + 1].replace(' ','')) * math.pi / 180))
        cVolts = np.append(cVolts, cValues) 
        j += 2              
    cVolts = np.append(cVolts, complex(0,0))  # adding the ground voltage (ideal)
    
    # Here we check for convergence
    VConv = []
    LastV = Str2CmplxArr(pars['Last_V'])

    for i in range(pars['NumPhases']):
        VConv.append(cmath.polar(cVolts[i])[0] - cmath.polar(LastV[i])[0])

 
    pars['Last_V'] = CmplxArr2Str(cVolts)
    Converged = abs(max(VConv)) <= 1e-5
    if not Converged:
    
        pars['iteration']   += 1
        # 1. Calculate the Amps contribution of the linear part based on the actual reading
        Ilin = np.dot(Yprim, cVolts.T)

        # 2. Calculate the nonlinear adjustment based on the device ratings
        Inlin = '['         # Delta current (Current injection vector)
        ITerm = '['         # I terminal (nonlinear current at the PCE terminals)
        DeltaI = 0.0        # Stores the delta I for the load
        for i in range(pars['NumPhases']):
           NLinI = np.conjugate((complex(pars['Load_PQ'])/pars['NumPhases'])/cVolts[i]) 
           DeltaI = Ilin[i] - NLinI 
           Inlin += Cmplx2Str(DeltaI) + ' ' 
           ITerm += Cmplx2Str(NLinI) + ' '
    
        Inlin += ']'
        ITerm += ']'

        # 3. Sends the Inj and terminal Currents and to DSS
        DSSText.Command = 'select Load.' + pars['Load_Name']
        DSSText.Command = 'set InjCurrent=' + Inlin 
        DSSText.Command = 'set ITerminal=' + ITerm 

        # 4. Tell DSS to run another iteration to check if this works
        DSSSolve = 'yes'
       
except Exception as e:
    pass
    error_type = type(e).__name__
    traceback.print_exc()
    DSSPipe.NeedsControlAction(DSSSolve)                # Indicates if the control action took place 2 DSS

finally:
    DSSPipe.NeedsControlAction(DSSSolve)                # Indicates if the control action took place 2 DSS



    
