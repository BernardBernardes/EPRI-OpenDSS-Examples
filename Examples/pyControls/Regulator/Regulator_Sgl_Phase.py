# -*- coding: utf-8 -*-
"""
Created on Thu Dec  5 10:23:05 2024

@author: Davis Montenegro

Implements a regulator using the pyControl object structure to be used within an
OpenDSS simulation. Use this structure as base for implementing your own
controls.
 
"""

import pywintypes
import sys

# Some globals
puV     = 0.0                                                 # Stores the actual Vpu at the bus observed
Target  = 1.0                                                 # This is the target
Band    = 0.01                                                # This is the error band for control
myXfmr = 'reg4c'
DSSQry = '? Transformer.'                                     # To prevent unnecessary copies

'''
Routine for parsing a DSS String into array of strings
'''  
def Str2StrArray(myString):
    myResult = myString.replace('[','').replace(']','').split(',')
    return myResult

    
# Here starts the control 
'''
This routine is for checking if a control action is required and notify OpenDSS about it
'''  
Result = 'no'                                                         # Indicates if the control action was needed
DSSText.Command = 'set class=transformer'
DSSText.Command = 'ClassMembers'                                      # Gets the list of Xfmrs (not needed, just as example)
Xfmrs = Str2StrArray(DSSText.Result)
if myXfmr in Xfmrs:
    try:
        # First, get the bus I'm interested in
        DSSText.Command = DSSQry + myXfmr + '.buses'
        myBuses = Str2StrArray(DSSText.Result)
        myBus = myBuses[1].split('.')[0].replace(' ','')            # Stores the bus name
        myBPhase = int(myBuses[1].split('.')[1].replace(' ',''))    # Stores the phase of interest (single phase)   

        # Gets some data from the Xfmr for control purposes
        DSSText.Command = DSSQry + myXfmr + '.kVs'                   # Voltage ratings
        myVratStr = Str2StrArray(DSSText.Result)[1]
        myVrat = float(myVratStr) * 1e3                             # voltage rating at the secondary
        
        # Second, get the voltage at this bus
        DSSText.Command = 'set Bus=' + myBus
        DSSText.Command = 'voltages'
        VperPhase = DSSText.Result.replace(' ','').split(',')
        myVolt = float(VperPhase[((myBPhase - 1) * 2)])
        puV = myVolt / myVrat                                       # Here is the actual Vpu
        DSSText.Command = 'Var @myVpu=' + str(puV)                  # Here stores the Vpu into DSS for later use
        # Finally, evaluate if is within band and if a control action is needed
        if (puV > (Target + Band)) | (puV < (Target - Band)):
            Result = 'yes'                                          # This to notify DSS that a control action took place
            DSSText.Command = 'Var @myVpu'                          # Gets back the value of Vpu stored in DSS memory
            puV = float(DSSText.Result)
            if puV == 0:
                puV = Target                                        # in case the variable was not created before
            # Get some xfmr features for calculations
            XfmrVals = []
            props = ['MaxTap', 'MinTap','NumTaps', 'Tap']
            DSSText.Command = DSSQry + myXfmr + '.wdg=2'            # Activate the winding of interest
            for myprop in props:
                DSSText.Command = DSSQry + myXfmr + '.' + myprop
                XfmrVals.append(float(DSSText.Result))
            
            # This to determine the tap movement direction (up or down)
            SMult = -1             
            if puV < Target:
                SMult = 1
            
            TapStep = ( ( XfmrVals[0] - XfmrVals[1] ) / XfmrVals[2] ) * SMult
    
            # Reduce the current tap 1 step and keeps going with the simulation
            DSSText.Command = DSSQry.replace('? ','') + myXfmr + '.' + props[3] + '=' + str(XfmrVals[3] + TapStep)            
    # This part is mandatory        
    except Exception as e:
        pass
        error_type = type(e).__name__
        traceback.print_exc()
        DSSPipe.NeedsControlAction(Result)                     # Something happened, cancel the ctrl action, tell DSS

    finally:
        DSSPipe.NeedsControlAction(Result)                     # Indicates if the control action took place 2 DSS
