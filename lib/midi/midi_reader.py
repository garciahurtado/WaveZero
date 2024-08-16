import struct


class MIDIReader:
    def __init__(self, filename):
        self.filename = filename
        self.format_type = None
        self.num_tracks = None
        self.time_division = None
        self.tracks = []

    def read_file(self):
        with open(self.filename, 'rb') as file:
            self.read_header(file)
            for _ in range(self.num_tracks):
                self.read_track(file)

    def read_header(self, file):
        chunk_type = file.read(4)
        if chunk_type != b'MThd':
            raise ValueError("Not a valid MIDI file")

        header_length = struct.unpack('>I', file.read(4))[0]
        if header_length != 6:
            raise ValueError("Unexpected header length")

        format_type, num_tracks, time_division = struct.unpack('>HHH', file.read(6))
        self.format_type = format_type
        self.num_tracks = num_tracks
        self.time_division = time_division

        print(f"Format Type: {self.format_type}")
        print(f"Number of Tracks: {self.num_tracks}")
        print(f"Time Division: {self.time_division}")

    def read_track(self, file):
        chunk_type = file.read(4)
        if chunk_type != b'MTrk':
            raise ValueError("Expected track chunk")

        track_length = struct.unpack('>I', file.read(4))[0]
        track_data = file.read(track_length)

        track_events = self.parse_track_events(track_data)
        self.tracks.append(track_events)

    def parse_track_events(self, track_data):
        events = []
        i = 0
        while i < len(track_data):
            delta_time, bytes_read = self.read_variable_length(track_data[i:])
            i += bytes_read

            event_type = track_data[i]
            i += 1

            if event_type & 0x80 == 0:
                # Running status, use previous event type
                i -= 1
                event_type = events[-1]['event_type']

            if event_type & 0xF0 == 0x80:  # Note Off
                events.append({
                    'delta_time': delta_time,
                    'event_type': 'Note Off',
                    'channel': event_type & 0x0F,
                    'note': track_data[i],
                    'velocity': track_data[i + 1]
                })
                i += 2
            elif event_type & 0xF0 == 0x90:  # Note On
                events.append({
                    'delta_time': delta_time,
                    'event_type': 'Note On',
                    'channel': event_type & 0x0F,
                    'note': track_data[i],
                    'velocity': track_data[i + 1]
                })
                i += 2
            elif event_type == 0xFF:  # Meta Event
                meta_type = track_data[i]
                i += 1
                length, bytes_read = self.read_variable_length(track_data[i:])
                i += bytes_read
                data = track_data[i:i + length]
                i += length
                events.append({
                    'delta_time': delta_time,
                    'event_type': 'Meta Event',
                    'meta_type': meta_type,
                    'data': data
                })
            else:
                # Other event types can be added here
                print(f"Unhandled event type: {hex(event_type)}")
                break

        return events

    def read_variable_length(self, data):
        value = 0
        bytes_read = 0
        for byte in data:
            value = (value << 7) | (byte & 0x7F)
            bytes_read += 1
            if byte & 0x80 == 0:
                break
        return value, bytes_read

    def print_events(self):
        for track_num, track in enumerate(self.tracks):
            print(f"\nTrack {track_num + 1}:")
            for event in track:
                print(f"  Delta Time: {event['delta_time']}")
                print(f"  Event Type: {event['event_type']}")
                if event['event_type'] in ['Note On', 'Note Off']:
                    print(f"    Channel: {event['channel']}")
                    print(f"    Note: {event['note']}")
                    print(f"    Velocity: {event['velocity']}")
                elif event['event_type'] == 'Meta Event':
                    print(f"    Meta Type: {hex(event['meta_type'])}")
                    print(f"    Data: {event['data']}")
                print()