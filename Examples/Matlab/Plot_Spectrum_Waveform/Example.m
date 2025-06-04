% Create DSS object
DSSObject = actxserver('OpenDSSEngine.DSS')
if ~DSSObject.Start(0),
disp('Unable to start openDSS');
      return
end;
DSSText = DSSObject.Text;
DSSCircuit = DSSObject.ActiveCircuit;
DSSSolution = DSSCircuit.Solution;
DSSReactor = DSSCircuit.Reactors;
% Compile a model        
DSSText.Command = 'Compile "C:\Users\pdmo005\Documents\OpenDSS\8500-Node\master.dss"';
DSSSolution.Solve;

% gets the values within the energy meter register for the active storage
Idx = DSSReactor.First;
myRName = DSSReactor.Name