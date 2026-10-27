"""Frame-quantized musical timing without accumulated rounding drift."""
import math

TEMPO_EFFECTS = ('motion-loop','motion-stutter','reset-pulse')
BEATS = (.25,.5,1,2,4)


def tempo_frames(effect,bpm,beats):
    if effect not in TEMPO_EFFECTS or type(bpm) not in (int,float) or not math.isfinite(bpm) or not 40<=bpm<=240:
        raise ValueError('Choose a supported effect and BPM from 40 through 240.')
    if type(beats) not in (int,float) or beats not in BEATS:
        raise ValueError('Choose 1/4, 1/2, 1, 2 or 4 beats.')
    frames = math.floor(24*60/bpm*beats+.5)
    minimum = 2 if effect=='motion-loop' else 4
    period=24*60/bpm*beats
    if not minimum<=math.floor(period) or math.ceil(period)>48:
        raise ValueError('This beat length cannot fit the effect. Choose a shorter/longer beat or different BPM.')
    return frames


def validate_tempo(transition):
    tempo=transition.get('tempo')
    if tempo is None:return
    if not isinstance(tempo,dict):raise ValueError('Invalid tempo settings.')
    frames=tempo_frames(transition.get('effect'),tempo.get('bpm'),tempo.get('beats'))
    if transition.get('loop_frames') != frames:
        raise ValueError('Tempo and movement interval differ; apply the BPM setting again.')



def musical_positions(effect,count,repeat,tempo):
    """Round each beat boundary, not one interval repeated with accumulating drift."""
    period=24*60/tempo['bpm']*tempo['beats']
    positions=[]
    beat=1
    if effect=='reset-pulse':
        previous=-1;boundary=math.floor(beat*period+.5)-1
        for i in range(count):
            if i==boundary:
                positions.append(-1)  # +1 in prediction_plan gives source I-VOP 0
                previous=i;beat+=1;boundary=math.floor(beat*period+.5)-1
            else:positions.append((i-previous-1)//repeat)
    else:
        start=0;boundary=math.floor(beat*period+.5)
        for i in range(count):
            if i==boundary:
                start=i;beat+=1;boundary=math.floor(beat*period+.5)
            if effect=='motion-loop':positions.append(i-start)
            else:positions.append(start if i-start<(boundary-start)//2 else i)
        if effect=='motion-stutter':
            release=count-max(2,count//4)
            positions[release:]=range(release,count)
    return positions
