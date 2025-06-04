# -*- coding: utf-8 -*-
"""
Created on Thu Jan  20 10:23:05 2025

@author: Davis Montenegro

Implements an IBR model for dynamics simulation. The IBR includes an PI controller
for controlling the averaged duty cycle when inverting the DC signal.
This model stores the local variables using python's local environment.

Each time step in the dynamics mode solution executes the following steps:
    
Increment_time;

{Predictor}
IterationFlag := 0;
IntegratePCStates;
SolveSnap;

{Corrector}
IterationFlag := 1;
IntegratePCStates;
SolveSnap;

The algorithm is currently a simple predictor-corrector method with one step of correction. 
The IterationFlag (IntegrationFlag) variable indicates to the integration routines whether 
the solution is in the predictor step or the corrector step.
Only PC elements have states that are integrated. Power Delivery (PD) elements are constant 
impedance elements simply defined by a primitive Y matrix
 
"""

import cmath, math
import json
import numpy as np
import traceback

# Connects to DSS through the PIPE
thismodelname = 'PVDyn_py'

parsRdy = False

if "pars" in locals():
    parsRdy = True

#%%
'''
Some subroutines
'''

DSSQry = '? PVSystem.' 

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
        'PV_Name'   :'myPV',                        # The name of the PV to control
        'PV_PQ'     : '600+0j',                     # This is the power we want for the PV (P + jQ) in kW and kvar
        'kV_rating' : 0.0,                          # The load kV rating LL
        'BasekV'    : 0.0,                          # Rating LN
        'Yprim'     : '',                           # THe Yprimitive for this model
        'NumCond'   : 3,                            # Number of conductors for the model (delta connected)
        'NumPhases' : 3,                            # Number of phases for the model
        'iteration' : 0,                            # Stores the number of iterations used by this model
        'integflag' : 1,                            # This is the flag for indicating the integration stage
        'kNum'      : 0.9502,                       # Coefficient at the numerator of the PI controller
        'kDen'      : 0.04979,                      # Coefficient at the denominaor of the PI controller
        'kp'        : 1e-5,                         # PI Controller gain
        'BaseZt'    : 0,                            # Z base
        'ImaxPhase' : 0,                            # Max current per phase
        'XThev'     : 0,                            # X Thevenin
        'RS'        : 0,                            # R Thevenin
        'Zthev'     : '0+0j',                       # Z Thevenin
        'YEQ'       : '0+0j',                       # Equivalent admittance
        'dit'       : [0, 0, 0],                    # Delta Current (derivative)
        'it'        : [0, 0, 0],                    # Current
        'ithistory' : [0, 0, 0],                    # Current history
        'mi'        : [0, 0, 0],                    # Duty factor for inverter
        'LS'        : 0,                            # IBR inductance
        'RatedVDC'  : 700,                          # DC rating for the IBR at the DC side
        'BaseFreq'  : 60,                           # 60 Hz by default
        'CtrlTol'   : 1e-3,                         # Tolerance of the PI control
        'PINum'     : [0, 0, 0, 0, 0, 0],           # PI control numerator (2 reg per phase)
        'PIDen'     : [0, 0, 0, 0, 0, 0],           # PI control denominator (2 reg per phase)
        'StepSize'  : 0                             # Simulation step size
        
        }
    
    print('Initializing...')
    # Since this is the first time, get values from DSS and save them locally
    # 1. Save the bus name
    DSSText.Command = DSSQry + pars['PV_Name'] + '.bus1'
    myBuses = Str2StrArray(DSSText.Result)
    pars['bus'] = myBuses[0].split('.')[0].replace(' ','')            # Stores the bus name


    # 2. Calculate and set the Y primitive
    DSSText.Command = DSSQry + pars['PV_Name'] + '.kV'
    pars['kV_rating'] = (float((DSSText.Result).replace(' ','')))                   # LL voltage
    pars['BasekV'] = (float((DSSText.Result).replace(' ',''))) / math.sqrt(3)       # LN voltage

    # Calculates thevenin equivalents
    DSSText.Command = 'get DefaultBaseFrequency'
    pars['BaseFreq'] = float(DSSText.Result)
    TotPow = complex(pars['PV_PQ'])
    kVA, KVAng = cmath.polar(TotPow)
    pars['BaseZt'] = 1e3 * ((pars['kV_rating']**2)/kVA)
    pars['XThev'] = 0.5 * pars['BaseZt']    # 50% R
    pars['RS'] = 0.5 * pars['BaseZt']       # 50% X
    pars['ImaxPhase'] = (kVA/pars['BasekV'])/pars['NumPhases']
    pars['Zthev'] = Cmplx2Str(complex(pars['RS'], pars['XThev']))
    pars['YEQ'] = Cmplx2Str(1 / complex(pars['Zthev']))
    pars['LS'] = pars['XThev'] / (2 * math.pi * pars['BaseFreq']) 

   
    # Get actual voltage at the point of connection
    DSSText.Command = 'set Bus=' + pars['bus']
    DSSText.Command = 'voltages'
    VperPhase = DSSText.Result.replace(' ','').split(',')
    j = 0
    cVolts = []
    for i in range(pars['NumPhases']):
        cValues = np.array(cmath.rect(float(VperPhase[j].replace(' ','')), float(VperPhase[j + 1].replace(' ','')) * math.pi / 180))
        cVolts = np.append(cVolts, cValues) 
        j += 2
    # pars['Last_V'] = CmplxArr2Str(cVolts)
    # Initializes duty cycle for the IBR controller and Initial current output
    for idx in range(pars['NumPhases']):
        Vmag, Vang = cmath.polar(cVolts[idx])
        pars['it'][idx] = ((TotPow.real * 1e3) / Vmag)/pars['NumPhases']
        if pars['it'][idx] > pars['ImaxPhase']:
            pars['it'][idx] = pars['ImaxPhase']
        pars['mi'][idx] = ((pars['RS'] * pars['it'][idx]) + Vmag) / pars['RatedVDC']
        if pars['mi'][idx] > 1:
            pars['mi'][idx] = 1 

    DSSText.Command = 'get StepSize'   # Gets the simulation step size
    pars['StepSize'] = float(DSSText.Result)

    # This is delta connected, then Yeq is:
    Yeq = complex(pars['YEQ']) / 3 # Delta impedance

    # The device is delta connected
    Yprim = np.zeros(pars['NumCond']**2, dtype=complex).reshape(pars['NumCond'],pars['NumCond'])
    for i in range(pars['NumPhases']):
        for j in range(pars['NumPhases']):
            if i == j:
                Yprim[i][j] = -2 * Yeq
            else:
                Yprim[i][j] = Yeq


    # Now send the Yprim to OpenDSS in the right format
    DSSYCmd = '['
    for i in range(pars['NumCond']):
        for j in range(i + 1):
            DSSYCmd += Cmplx2Str(Yprim[i][j]) + ' '
        if i < (pars['NumPhases'] - 1):
            DSSYCmd += '| '
    DSSYCmd += ']'
    DSSText.Command = 'select PVSystem.' + pars['PV_Name']
    DSSText.Command = 'set Yprim=' + DSSYCmd
    
    pars['Yprim'] = Yprim
    
    print('Model initialized')
        
else:
    print('Model already initialized')

#%%
'''
The PV System model starts here, this section represents the integration
step. It is composed by 2 steps for trapezoidal integration (default in DSS).
The integration will be called twice, first to predict and then to correct.
The step is identified with the variable "integflag", stored in the models state
variables
'''  
DSSSolve = 'no'
try:
    
    
    # Check the simulation mode
    DSSText.Command = 'get mode' 
    SimMode = DSSText.Result
    
    # Check in which integration stage are we
    DSSText.Command = 'get IntegrationFlag'
    NewFlg = int(DSSText.Result)

    # it only does the integration if the integration flag at OpenDSS has changed
    if (pars['integflag'] != NewFlg) and (SimMode.lower() == 'dynamic'):
        
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
        
        LastV = Str2CmplxArr(pars['Last_V'])   
        pars['Last_V'] = CmplxArr2Str(cVolts)

        pars['integflag'] = NewFlg
        pars['iteration']   += 1
        Yprim = pars['Yprim']             # Gets back the Yprim

        for i in range(pars['NumPhases']):
            # 1. Calculate history based on previous integrations
            
            if pars['integflag'] == 0:
                pars['ithistory'][i] = pars['it'][i] + (0.5 * pars['StepSize'] * pars['dit'][i])
                
            Vmag, Vang = cmath.polar(cVolts[i]) # saving voltage for this phase as polar
            # 2. Determine actual current per phase
            ISP = ((complex(pars['PV_PQ']).real * 1e3) / Vmag ) / pars['NumPhases']
            if ISP > pars['ImaxPhase']:
                ISP = pars['ImaxPhase']
              
            # This model has no voltage safety constraints -  keep it in mind
            # 3. Calcualte the integration and derivative for the current per phase
            # 3.1. Go for the modulation coefficient (PI control -> duty cycle)
            if pars['integflag'] != 0:
                iError = ISP - pars['it'][i]
                iErrorPct = iError/ISP
                if abs(iErrorPct) > pars['CtrlTol']:
                    # The PI controller is in the form: Y(Z) = kNum * U(Z-1) + kDen * Y(Z-1) ; U(Z) = kp * Error
                    PIPhase = 2 * i   # This allows to differentiate per phase
                    pars['PINum'][PIPhase]      = pars['PINum'][PIPhase + 1]  # Memory shift
                    pars['PINum'][PIPhase + 1]  = iError * pars['kp']
                    pars['PIDen'][PIPhase]      = pars['PIDen'][PIPhase + 1]  # Memory shift
                    pars['PIDen'][PIPhase + 1]  = (pars['PINum'][PIPhase] * pars['kNum']) + (pars['PIDen'][PIPhase] * pars['kDen'])
                    iDelta                      = pars['PIDen'][PIPhase + 1]
                    myDCycle                    = pars['mi'][i] + iDelta
                    if (myDCycle <= 1) and (myDCycle > 0):
                        pars['mi'][i] = myDCycle
            # 3.2. Calculate differential for next iteration
            pars['dit'][i] = ((pars['mi'][i] * pars['RatedVDC']) - (pars['RS']*pars['it'][i]) - Vmag) / pars['LS']
            
            # 3.3 Set the current for the phase
            pars['it'][i] = pars['ithistory'][i] + (0.5 * pars['StepSize'] * pars['dit'][i])

            if abs(pars['it'][i]) > pars['ImaxPhase']:
                pars['it'][i] = pars['ImaxPhase']
       
        Ilin = np.dot(Yprim, cVolts.T)
        # 4. Set the current arrays for the next solution
        Inlin = '['         # Delta current (Current injection vector)
        ITerm = '['         # I terminal (nonlinear current at the PCE terminals)
        DeltaI = 0.0        # Stores the delta I for the load
        for i in range(pars['NumPhases']):
            Vmag, Vang = cmath.polar(cVolts[i])         # Volts as polar
            NLinI = -1 * cmath.rect(pars['it'][i], Vang)     # FP = 1, only active power
            DeltaI = Ilin[i] - NLinI 
            Inlin += Cmplx2Str(DeltaI) + ' ' 
            ITerm += Cmplx2Str(NLinI) + ' '
        
        Inlin += ']'
        ITerm += ']'
        
        # 5. Sends the Inj and terminal Currents and to DSS
        DSSText.Command = 'select PVSystem.' + pars['PV_Name']
        DSSText.Command = 'set InjCurrent=' + Inlin 
        DSSText.Command = 'set ITerminal=' + ITerm 
        
        # 6. Tell DSS to run another iteration to check if this works
        DSSSolve = 'yes'
       
except Exception as e:
    pass
    error_type = type(e).__name__
    traceback.print_exc()

finally:
    DSSPipe.NeedsControlAction(DSSSolve)                # Indicates if the control action took place 2 DSS



    
