# Afterglow for iPhone: gets a song on the phone itself, inside the free app "a-Shell".
#
# The Afterglow page starts it through a link (ashell:...), with the song's link or its name as one
# word of hex digits. It can also be run by hand:   python3 afterglow.py <link or name>
# The song is saved, with its title, artist and cover inside the file, in a-Shell's folder "Afterglow"
# (Files app > On My iPhone > a-Shell > Afterglow). In Afterglow: Add music > From this phone.
#
# Everything here is plain Python: the phone has no ffmpeg, so nothing is converted. The audio is taken
# as the site offers it (M4A or MP3) and the tags are written with "mutagen".
import os
import re
import sys
import time
import urllib.request

OUT = os.environ.get('AFTERGLOW_OUT') or os.path.join(os.path.expanduser('~'), 'Documents', 'Afterglow')
STAMP = os.path.join(OUT, '.downloader')
NEEDED = ['yt-dlp', 'yt-dlp-ejs', 'mutagen'] + (['yt-dlp-apple-webkit-jsi'] if sys.platform in ('darwin', 'ios') else [])
FRESH_DAYS = 4      # the downloader is brought up to date this often: the sites change all the time


def say(*parts):
    print(*parts, flush=True)


def have(module):
    try:
        __import__(module)
        return True
    except Exception:
        return False


def install():
    """The downloader itself (yt-dlp and what it needs), from PyPI. All of it is plain Python."""
    wanted = ['install', '-U', '-q', '--disable-pip-version-check'] + NEEDED
    code = 1
    if sys.platform not in ('darwin', 'ios') and sys.executable:      # a computer: pip in a process of its own
        try:
            import subprocess
            code = subprocess.call([sys.executable, '-m', 'pip'] + wanted)
        except Exception:
            code = 1
    if code != 0:                                                      # the phone: here, in this same process
        try:
            from pip._internal.cli.main import main as pip
            code = pip(wanted)
        except SystemExit as e:
            code = e.code or 0
        except Exception as e:
            say('  (pip:', e, ')')
            code = 1
        try:
            import logging
            logging.disable(logging.CRITICAL)                          # pip's own remarks about what is loaded afterwards
        except Exception:
            pass
    if code == 0:
        try:
            open(STAMP, 'w').write(str(int(time.time())))
        except OSError:
            pass
    import importlib
    importlib.invalidate_caches()
    return code == 0


def ready():
    os.makedirs(OUT, exist_ok=True)
    try:
        old = time.time() - os.path.getmtime(STAMP) > FRESH_DAYS * 86400
    except OSError:
        old = True
    # Brought up to date BEFORE it is loaded: once loaded, this run keeps the version it has.
    if not have('yt_dlp') or not have('mutagen') or old:
        say('Getting the downloader ready. The first time takes a minute or two...' if not have('yt_dlp') else 'Bringing the downloader up to date...')
        install()
    if not have('yt_dlp'):
        say('\nThe downloader is being set up. Go back to Afterglow and tap Download once more.')
        say('(If this shows every time: check the internet.)')
        return False
    return True


JUNK = re.compile(r'\s*[\(\[\{](?:[^\)\]\}]*\b(?:official|video|audio|lyrics?|visuali[sz]er|hd|hq|4k|mv|m/v|explicit|clean)\b[^\)\]\}]*)[\)\]\}]', re.I)


def names(info):
    """Title, artist and album as a music app shows them, from what the site says about the video."""
    title = (info.get('track') or '').strip()
    artist = (info.get('artist') or '').strip()
    if not title:
        raw = JUNK.sub('', info.get('title') or '').strip(' -|') or (info.get('title') or 'Untitled')
        split = re.match(r'^(.{1,80}?)\s+[-–—|]\s+(.+)$', raw)
        if split:
            artist = artist or split.group(1).strip()
            title = split.group(2).strip()
        else:
            title = raw
    if not artist:
        artist = re.sub(r'\s*-\s*Topic$', '', info.get('channel') or info.get('uploader') or '').strip()
    artists = info.get('artists')
    if isinstance(artists, list) and artists and info.get('track'):
        artist = ', '.join(a for a in artists if a)
    return title or 'Untitled', artist, (info.get('album') or '').strip()


def fetch(url, most=4 << 20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as r:
            data = r.read(most + 1)
        return data if 1000 < len(data) <= most else None
    except Exception:
        return None


def cover(info):
    """The picture, as JPEG or PNG bytes (those are the two kinds a song file can carry)."""
    tries = []
    if info.get('extractor_key') == 'Youtube' and info.get('id'):
        base = 'https://i.ytimg.com/vi/%s/' % info['id']
        tries = [base + n for n in ('maxresdefault.jpg', 'hq720.jpg', 'mqdefault.jpg')]     # the wide ones: no black bars
    for t in reversed(info.get('thumbnails') or []):
        u = t.get('url') or ''
        if re.search(r'\.(jpe?g|png)(\?|$)', u, re.I):
            tries.append(u)
    if info.get('thumbnail'):
        tries.append(info['thumbnail'])
    for u in tries[:6]:
        data = fetch(u)
        if data and data[:3] == b'\xff\xd8\xff':
            return data, 'jpeg'
        if data and data[:8] == b'\x89PNG\r\n\x1a\n':
            return data, 'png'
    return None, None


def tag(path, title, artist, album, picture, kind):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in ('.m4a', '.mp4', '.m4b'):
            try:
                plain_m4a(path)
            except Exception:
                pass
            # (If it could not be rewritten: at least it does not call itself "dash", which some players refuse.)
            with open(path, 'r+b') as f:
                head = f.read(12)
                if head[4:8] == b'ftyp' and head[8:12] == b'dash':
                    f.seek(8)
                    f.write(b'M4A ')
            from mutagen.mp4 import MP4, MP4Cover
            m = MP4(path)
            m['\xa9nam'] = [title]
            if artist:
                m['\xa9ART'] = [artist]
            if album:
                m['\xa9alb'] = [album]
            if picture:
                m['covr'] = [MP4Cover(picture, imageformat=MP4Cover.FORMAT_PNG if kind == 'png' else MP4Cover.FORMAT_JPEG)]
            m.save()
        elif ext == '.mp3':
            from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, APIC
            try:
                m = ID3(path)
            except ID3NoHeaderError:
                m = ID3()
            m.setall('TIT2', [TIT2(encoding=3, text=[title])])
            if artist:
                m.setall('TPE1', [TPE1(encoding=3, text=[artist])])
            if album:
                m.setall('TALB', [TALB(encoding=3, text=[album])])
            if picture:
                m.setall('APIC', [APIC(encoding=3, mime='image/' + kind, type=3, desc='Cover', data=picture)])
            m.save(path, v2_version=3)
    except Exception as e:
        say('  (the title and cover could not be written into the file:', e, ')')


def boxes(data, start, end):
    """The boxes of an MP4 between two places: (type, where its content starts, where it ends, where it starts)."""
    at = start
    while at + 8 <= end:
        size = int.from_bytes(data[at:at + 4], 'big')
        head = 8
        if size == 1:
            size = int.from_bytes(data[at + 8:at + 16], 'big')
            head = 16
        elif size == 0:
            size = end - at
        if size < head or at + size > end:
            break
        yield data[at + 4:at + 8], at + head, at + size, at
        at += size


def child(data, start, end, kind):
    for t, a, b, _ in boxes(data, start, end):
        if t == kind:
            return a, b
    return None


def box(kind, *parts):
    body = b''.join(parts)
    return (len(body) + 8).to_bytes(4, 'big') + kind + body


def u32(n):
    return int(n).to_bytes(4, 'big')


def plain_m4a(path):
    """
    A song as YouTube gives it is an M4A in pieces (each a 'moof' with its 'mdat'), and calls itself 'dash'.
    Some players refuse that. This writes the same sound, untouched, as one plain M4A: the list of its
    samples in the header, then the sound. True if it was rewritten; False (file untouched) for anything
    it is not sure about.
    """
    with open(path, 'rb') as f:
        data = f.read()
    end = len(data)
    top = list(boxes(data, 0, end))
    if not any(t == b'moof' for t, _, _, _ in top):
        return False                                           # not in pieces: nothing to do
    moov = next(((a, b) for t, a, b, _ in top if t == b'moov'), None)
    if not moov:
        return False
    traks = [(a, b) for t, a, b, _ in boxes(data, *moov) if t == b'trak']
    if len(traks) != 1:
        return False
    mdia = child(data, traks[0][0], traks[0][1], b'mdia')
    minf = mdia and child(data, mdia[0], mdia[1], b'minf')
    stbl = minf and child(data, minf[0], minf[1], b'stbl')
    stsd = stbl and child(data, stbl[0], stbl[1], b'stsd')
    mdhd = mdia and child(data, mdia[0], mdia[1], b'mdhd')
    mvhd = child(data, moov[0], moov[1], b'mvhd')
    if not (stsd and mdhd and mvhd):
        return False
    if b'enca' in data[stsd[0]:stsd[1]]:
        return False                                           # protected sound: left alone
    media_scale = int.from_bytes(data[mdhd[0] + (20 if data[mdhd[0]] == 1 else 12):][:4], 'big')
    movie_scale = int.from_bytes(data[mvhd[0] + (20 if data[mvhd[0]] == 1 else 12):][:4], 'big')
    usual_duration = usual_size = 0
    mvex = child(data, moov[0], moov[1], b'mvex')
    trex = mvex and child(data, mvex[0], mvex[1], b'trex')
    if trex:
        usual_duration = int.from_bytes(data[trex[0] + 12:trex[0] + 16], 'big')
        usual_size = int.from_bytes(data[trex[0] + 16:trex[0] + 20], 'big')

    sizes, durations, sound = [], [], []
    for t, a, b, begin in top:
        if t != b'moof':
            continue
        for t2, a2, b2, _ in boxes(data, a, b):
            if t2 != b'traf':
                continue
            base, each_duration, each_size, follow = begin, usual_duration, usual_size, None
            for t3, a3, b3, _ in boxes(data, a2, b2):
                if t3 == b'tfhd':
                    flags = int.from_bytes(data[a3 + 1:a3 + 4], 'big')
                    at = a3 + 8
                    if flags & 0x1:
                        base = int.from_bytes(data[at:at + 8], 'big')
                        at += 8
                    if flags & 0x2:
                        at += 4
                    if flags & 0x8:
                        each_duration = int.from_bytes(data[at:at + 4], 'big')
                        at += 4
                    if flags & 0x10:
                        each_size = int.from_bytes(data[at:at + 4], 'big')
                elif t3 == b'trun':
                    flags = int.from_bytes(data[a3 + 1:a3 + 4], 'big')
                    count = int.from_bytes(data[a3 + 4:a3 + 8], 'big')
                    at = a3 + 8
                    where = follow if follow is not None else base
                    if flags & 0x1:
                        offset = int.from_bytes(data[at:at + 4], 'big', signed=True)
                        where = base + offset
                        at += 4
                    if flags & 0x4:
                        at += 4
                    for _ in range(count):
                        d, n = each_duration, each_size
                        if flags & 0x100:
                            d = int.from_bytes(data[at:at + 4], 'big')
                            at += 4
                        if flags & 0x200:
                            n = int.from_bytes(data[at:at + 4], 'big')
                            at += 4
                        if flags & 0x400:
                            at += 4
                        if flags & 0x800:
                            at += 4
                        if n <= 0 or where + n > end:
                            return False
                        sizes.append(n)
                        durations.append(d)
                        sound.append(data[where:where + n])
                        where += n
                    follow = where
    if not sizes or not media_scale or not movie_scale:
        return False
    total = sum(durations)

    # The lists of the plain form. Samples go 43 to a chunk (about a second of sound).
    runs = []
    for d in durations:
        if runs and runs[-1][1] == d:
            runs[-1][0] += 1
        else:
            runs.append([1, d])
    stts = box(b'stts', u32(0), u32(len(runs)), *(u32(n) + u32(d) for n, d in runs))
    per = 43
    chunks = (len(sizes) + per - 1) // per
    last = len(sizes) - (chunks - 1) * per
    entries = [u32(1) + u32(per) + u32(1)] if chunks > 1 else []
    if last != per or chunks == 1:
        entries.append(u32(chunks) + u32(last) + u32(1))
    stsc = box(b'stsc', u32(0), u32(len(entries)), *entries)
    stsz = box(b'stsz', u32(0), u32(0), u32(len(sizes)), *(u32(n) for n in sizes))
    starts, at = [], 0
    for i, n in enumerate(sizes):
        if i % per == 0:
            starts.append(at)
        at += n

    def timed(kind, a, b, units):
        """A header box with its length set: 'mvhd' and 'tkhd' count in the movie's units, 'mdhd' in the sound's."""
        raw = bytearray(data[a:b])
        long = raw[0] == 1
        where = {b'mvhd': 24 if long else 16, b'tkhd': 28 if long else 20, b'mdhd': 24 if long else 16}[kind]
        raw[where:where + (8 if long else 4)] = int(units).to_bytes(8 if long else 4, 'big')
        return box(kind, bytes(raw))

    def again(a, b, first):
        """The header, built again: lengths set, the lists put in, and what belongs to the pieces left out."""
        out = []
        for t, x, y, begin in boxes(data, a, b):
            if t == b'mvex':
                continue
            if t in (b'trak', b'mdia', b'minf'):
                out.append(box(t, again(x, y, first)))
            elif t == b'mvhd' or t == b'tkhd':
                out.append(timed(t, x, y, total * movie_scale // media_scale))
            elif t == b'mdhd':
                out.append(timed(t, x, y, total))
            elif t == b'stbl':
                stco = box(b'stco', u32(0), u32(len(starts)), *(u32(first + s) for s in starts))
                out.append(box(b'stbl', box(b'stsd', data[stsd[0]:stsd[1]]), stts, stsc, stsz, stco))
            else:
                out.append(data[begin:y])
        return b''.join(out)

    ftyp = box(b'ftyp', b'M4A ', u32(0), b'M4A ', b'mp42', b'isom')
    size = len(box(b'moov', again(moov[0], moov[1], 0)))
    header = box(b'moov', again(moov[0], moov[1], len(ftyp) + size + 8))
    if len(header) != size:
        return False
    body = b''.join(sound)
    if len(ftyp) + len(header) + 8 + len(body) >= 1 << 32:
        return False
    temp = path + '.plain'
    with open(temp, 'wb') as f:
        f.write(ftyp + header + (len(body) + 8).to_bytes(4, 'big') + b'mdat' + body)
    try:                                                       # looked at once more before it takes the file's place
        from mutagen.mp4 import MP4
        if abs(MP4(temp).info.length - total / media_scale) > 0.5:
            raise ValueError('length')
        os.replace(temp, path)
        return True
    except Exception:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False


def clean(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip(' .')[:120] or 'Song'


def finish(info):
    got = (info.get('requested_downloads') or [{}])[0].get('filepath') or info.get('filepath')
    if not got or not os.path.isfile(got):
        return None
    title, artist, album = names(info)
    picture, kind = cover(info)
    tag(got, title, artist, album, picture, kind)
    ext = os.path.splitext(got)[1]
    want = os.path.join(OUT, clean((artist + ' - ' if artist else '') + title) + ext)
    if os.path.abspath(want) != os.path.abspath(got):
        try:
            os.replace(got, want)
            got = want
        except OSError:
            pass
    say('Saved:', os.path.basename(got))
    return got


def choose(words):
    """The song's name was typed: the first results are shown, and one is chosen."""
    import yt_dlp
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': True, 'skip_download': True}) as y:
        found = y.extract_info('ytsearch6:' + words, download=False)
    items = [e for e in (found.get('entries') or []) if e and e.get('id')]
    if not items:
        say('Nothing found for:', words)
        return None
    say('\nFound for "%s":' % words)
    for i, e in enumerate(items, 1):
        seconds = int(e.get('duration') or 0)
        say('  %d. %s  -  %s%s' % (i, e.get('title') or '?', e.get('channel') or e.get('uploader') or '', '  (%d:%02d)' % divmod(seconds, 60) if seconds else ''))
    pick = os.environ.get('AFTERGLOW_PICK')
    if pick is None:
        try:
            pick = input('\nType the number and press return (just return = 1, 0 = none): ').strip()
        except EOFError:
            pick = ''
    number = int(pick) if pick.isdigit() else 1
    if number < 1 or number > len(items):
        say('Nothing chosen.')
        return None
    return items[number - 1].get('url') or 'https://www.youtube.com/watch?v=' + items[number - 1]['id']


def download(url):
    import yt_dlp
    shown = [-1]

    def progress(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            part = int(d.get('downloaded_bytes', 0) * 100 / total) if total else -1
            if part >= 0 and part // 10 != shown[0]:
                shown[0] = part // 10
                say('  %d%%' % part)
        elif d.get('status') == 'finished':
            shown[0] = -1

    options = {
        # Audio only, in a kind the iPhone plays as it is (nothing can be converted here), plain downloads first.
        'format': 'bestaudio[ext=m4a][protocol^=http]/bestaudio[ext=mp3][protocol^=http]/bestaudio[ext=m4a]/bestaudio[ext=mp3]/best[ext=mp4][protocol^=http]',
        'outtmpl': os.path.join(OUT, '%(id)s.%(ext)s'),
        'noplaylist': 'list=' not in url or 'watch?v=' in url,
        'playlistend': 100,
        'quiet': True, 'no_warnings': True, 'noprogress': True, 'no_color': True,
        'progress_hooks': [progress], 'fixup': 'never', 'retries': 5, 'fragment_retries': 5,
        'ignoreerrors': 'only_download', 'windowsfilenames': True,
    }
    with yt_dlp.YoutubeDL(options) as y:
        info = y.extract_info(url, download=True)
    if not info:
        return []
    entries = [e for e in (info.get('entries') or []) if e] if info.get('_type') == 'playlist' else [info]
    return [f for f in (finish(e) for e in entries) if f]


def main(args):
    if not args:
        say('Give a link or the name of a song.')
        return 1
    text = args[0]
    if len(args) == 1 and re.fullmatch(r'(?:[0-9a-f]{2})+', text):          # as the Afterglow page sends it
        try:
            text = bytes.fromhex(text).decode('utf-8')
        except ValueError:
            pass
    else:
        text = ' '.join(args)
    text = text.strip()
    say('Afterglow: getting "%s"' % text)
    if not ready():
        return 1
    try:
        url = text if re.match(r'https?://', text) else choose(text)
        if not url:
            return 1
        say('Downloading...')
        saved = download(url)
    except KeyboardInterrupt:
        say('\nStopped.')
        return 1
    except Exception as e:
        saved = []
        say('\nIt did not work:', str(e).replace('ERROR: ', '')[:300])
        try:
            os.remove(STAMP)            # the next try brings the downloader up to date first
        except OSError:
            pass
    if not saved:
        say('\nNothing was saved. Try again in a minute, or try another link for the same song.')
        return 1
    say('\nDone: %d song%s in the folder "Afterglow".' % (len(saved), '' if len(saved) == 1 else 's'))
    say('Now go back to Afterglow: Add music > From this phone > a-Shell > Afterglow, and pick %s.' % ('it' if len(saved) == 1 else 'them'))
    return 0


if __name__ == '__main__':
    main(sys.argv[1:])
