"""Preloaded crowd excerpts, synchronized with the bankruptcy presentation."""
import random

import pygame
from sound_assets import load_sound


_random = random.SystemRandom()  # Cosmetic audio must not change game rolls.
FADE_IN_MS = 140
FADE_OUT_MS = 400
CROWD_VOLUME = 0.7


def preload(page):
    if getattr(page, '_bankruptcy_crowd_source', None) is None:
        source = load_sound('Sounds/Crowd.wav')
        if source is not None:
            page._bankruptcy_crowd_source = source
            page._bankruptcy_crowd_pcm = source.get_raw()


def start(page, duration_ms):
    stop(page)
    preload(page)
    source = getattr(page, '_bankruptcy_crowd_source', None)
    mixer = pygame.mixer.get_init()
    if source is None or mixer is None:
        return
    rate, bits, channels = mixer
    frame_bytes = abs(bits) // 8 * channels
    pcm = page._bankruptcy_crowd_pcm
    total_frames = len(pcm) // frame_bytes
    frames = round(rate * duration_ms / 1000)
    if total_frames < frames:
        # A replacement shorter than the animation still supplies a full clip.
        if not pcm:
            return
        pcm = pcm * ((frames + total_frames - 1) // total_frames)
        total_frames = len(pcm) // frame_bytes
    last_start = total_frames - frames
    first_start = min(rate, last_start)
    offset = _random.randint(first_start, last_start) * frame_bytes
    clip = pygame.mixer.Sound(buffer=pcm[offset:offset + frames * frame_bytes])
    clip.set_volume(source.get_volume())
    channel = pygame.mixer.find_channel()
    if channel is None:
        return
    channel.set_volume(0)
    channel.play(clip)
    page._bankruptcy_crowd_playback = (channel, clip, duration_ms)


def update(page, elapsed_ms):
    playback = getattr(page, '_bankruptcy_crowd_playback', None)
    if playback is None:
        return
    channel, clip, duration = playback
    if channel.get_sound() is not clip:
        page._bankruptcy_crowd_playback = None
        return
    if elapsed_ms >= duration:
        stop(page)
        return
    clip.set_volume(page._bankruptcy_crowd_source.get_volume())
    envelope = max(0, min(1, elapsed_ms / FADE_IN_MS,
                          (duration - elapsed_ms) / FADE_OUT_MS))
    channel.set_volume(CROWD_VOLUME * envelope)


def pause(page, paused):
    playback = getattr(page, '_bankruptcy_crowd_playback', None)
    if playback is not None:
        channel, clip, _ = playback
        if channel.get_sound() is clip:
            if paused:
                channel.pause()
            else:
                channel.unpause()


def stop(page):
    playback = getattr(page, '_bankruptcy_crowd_playback', None)
    if playback is not None:
        channel, clip, _ = playback
        if channel.get_sound() is clip:
            channel.stop()
    page._bankruptcy_crowd_playback = None
