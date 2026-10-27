"""Validated, meaningful preset/tempo settings shared with the simple editor."""
import math
from effects import EFFECTS, prediction_plan

PRESETS = {
    'classic-mosh': [dict(duration=.5),dict(duration=1.5),dict(duration=3)],
    'frame-melt': [dict(duration=1,repeat=2,smooth=True),dict(duration=2,repeat=4,smooth=True),dict(duration=3,repeat=8,smooth=True)],
    'progressive-melt': [dict(duration=1,repeat=2,smooth=True),dict(duration=2,repeat=5,smooth=True),dict(duration=3,repeat=10,smooth=True)],
    'motion-loop': [dict(duration=1.5,loop_frames=16),dict(duration=2,loop_frames=8),dict(duration=3,loop_frames=4)],
    'loop-release': [dict(duration=1.5,loop_frames=12),dict(duration=2,loop_frames=8),dict(duration=3,loop_frames=4)],
    'motion-stutter': [dict(duration=1.5,loop_frames=16,smooth=True),dict(duration=2,loop_frames=8,smooth=True),dict(duration=3,loop_frames=4,smooth=True)],
    'reset-pulse': [dict(duration=1.5,loop_frames=24,repeat=2),dict(duration=2,loop_frames=12,repeat=4),dict(duration=3,loop_frames=6,repeat=8)],
}
from tempo import tempo_frames, validate_tempo


def preset_settings(effect,index,frame_count):
    if effect not in PRESETS or type(index) is not int or not 0<=index<3:
        raise ValueError('Choose a supported effect preset.')
    if type(frame_count) is not int or not 2<=frame_count<=2880:
        raise ValueError('Invalid incoming clip length.')
    config=dict(PRESETS[effect][index],effect=effect,motion_start=0,ending='flow')
    minimum=12 if effect in ('progressive-melt','motion-stutter','reset-pulse','loop-release') else 3 if effect=='motion-loop' else 1
    count=min(round(config['duration']*24),frame_count-1)
    if count<minimum:raise ValueError('Incoming clip is too short for this preset.')
    config['duration']=count/24
    if 'loop_frames' in config: config['loop_frames']=min(config['loop_frames'],count-1)
    prediction_plan(frame_count,effect,count,config.get('repeat',4),0,config.get('loop_frames'),config.get('smooth',False))
    return config


def validate_project_settings(frames,transitions):
    if not isinstance(frames,list) or not 1<=len(frames)<=12 or not all(type(n) is int and 2<=n<=2880 for n in frames):
        raise ValueError('Invalid project source lengths.')
    if not isinstance(transitions,list) or len(transitions)!=len(frames)-1:
        raise ValueError('One transition is needed per boundary.')
    for frame_count,config in zip(frames[1:],transitions):
        if not isinstance(config,dict):raise ValueError('Invalid project transition.')
        effect=config.get('effect')
        if effect=='cut':continue
        if effect not in EFFECTS:raise ValueError('Unsupported project effect.')
        duration=config.get('duration')
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 1/24<=duration<=min(6,(frame_count-1)/24):raise ValueError('Invalid project duration.')
        if config.get('ending','flow') not in ('flow','reset'):raise ValueError('Invalid effect ending.')
        validate_tempo(config)
        smooth=config.get('smooth',False) if effect in ('frame-melt','progressive-melt','motion-stutter') else False
        prediction_plan(frame_count,effect,round(duration*24),config.get('repeat',4),config.get('motion_start',0),config.get('loop_frames'),smooth,config.get('release_duration') if smooth else None,config.get('tempo'))
