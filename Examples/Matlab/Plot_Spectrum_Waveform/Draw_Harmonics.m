clear all;
% Create DSS object
DSSObject = actxserver('OpenDSSEngine.DSS');
if ~DSSObject.Start(0),
disp('Unable to start openDSS');
      return
end;
DSSText = DSSObject.Text;
DSSCircuit = DSSObject.ActiveCircuit;
DSSSolution = DSSCircuit.Solution;
DSSMonitors = DSSCircuit.Monitors;
% Compile a model        
DSSText.Command = ['Compile "' cd '\IEEE_519.dss"'];
DSSSolution.Solve;

DSSMonitors.Name = 'MPCC'; 

%Request the Bytestream
Freqs = DSSMonitors.ByteStream; 
% To adjust the matrix
iMonitorDataSize = typecast(Freqs(9:12),'int32'); 
%Adjusts the content
VIMonitor = typecast(Freqs(273:end),'single'); 
VIMonitor_reg = reshape(VIMonitor, iMonitorDataSize+2, [])';

% IN VIMonitor_reg the cols are as follows:
% Freq, Harmonic num, V1, Angle1, V2, Angle2, V3, Angle3, I1, AngleI1, I2, AngleI2, I3, AngleI3         

Fs = 8000;                   % samples per second
dt = 1/Fs;                   % seconds per sample
Fc = VIMonitor_reg(1,1);     % Fundamental Freq (Hz)
Num_P = 3;                   % Number of periods to draw
StopTime = 1/Fc * Num_P;     % seconds
t = (0:dt:StopTime-dt)';     % seconds

% The monitor has 2 samples for 2 different loading conditions, we can
% chosse which to use, in this case, I'll use the second one

Blk_2Use = 2;

Blk_shift = (Blk_2Use - 1) * 16;
DataSeg = VIMonitor_reg(Blk_shift + 1:((Blk_2Use) * 16), 1:14);
DataSz = size(DataSeg);

figure;

Num_Phases = 3;                     % 3phases to plot

% It will plot the current harmonics for all phases, going phase by phase
for j = 1:Num_Phases,                        
    Xtotal = zeros(size(t));
    for i = 1:DataSz(2),
        %%Sine wave per each harmonic (Amps), phase A:
        x = DataSeg(i,9 + 2*(j - 1))*sin(2*pi*DataSeg(i,1)*t + (DataSeg(i,10 + 2*(j - 1))*pi/180));
        Xtotal = Xtotal + x;
    end;
    
    % Plot the signal versus time:

    plot(t,Xtotal);
    hold on;
    xlabel('time (in seconds)');
    title('Signal versus Time');
end;

