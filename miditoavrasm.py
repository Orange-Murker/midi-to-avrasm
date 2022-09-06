import os.path
import sys
import getopt
import random
import mido

cpu_freq = 16.0


def time_to_cycles(time):
    ops = cpu_freq * 1000000
    return round(ops * time)


def tabbify(text):
    if text:
        return "    " + "\n    ".join(text.split("\n"))
    return ""


def generate_wait(unique_label, cycles, first_register, busy_code, busy_cycles):
    output = ""

    if cycles == 0:
        return ""
    elif cycles <= 12:
        while cycles >= 3:
            output += "    lpm\n"

        if cycles == 2:
            output += "    rjmp PC+1\n"

        elif cycles == 1:
            output += "    nop\n"
        return

    loop_max_length = [3 + busy_cycles]
    total_cycle_length = 3 + busy_cycles

    while cycles > 256 * total_cycle_length - 1 + 3:
        # -1 because the last cycle goes through brne +3 because of the cycles required
        # to decrement the outer loop
        total_cycle_length = 256 * total_cycle_length - 1 + 3

        loop_max_length.append(total_cycle_length)

    # Last loop iteration is one cycle less because brne falls through
    # ldi and last iteration cancels out len(loop_max_length) - len(loop_max_length)

    # All loops except for the last one
    cycles -= (len(loop_max_length) - 1) * 3

    loop_lengths = []
    for i in reversed(range(0, len(loop_max_length))):
        cycle_times = cycles // loop_max_length[i]

        if i != 0:
            if cycle_times + 1 == 256:
                cycle_times = -1
            loop_lengths.append(cycle_times + 1)
        else:
            loop_lengths.append(cycle_times)

        cycles = cycles % loop_max_length[i]

    for i, loop_length in enumerate(loop_lengths):
        output += "ldi r{}, {}\n".format(first_register + i, loop_length)

    output += "{}:\n{}".format(unique_label, tabbify(busy_code))

    for i in reversed(range(0, len(loop_lengths))):
        output += "    dec r{}\n    brne {}\n".format(first_register + i, unique_label)

    if cycles <= 12:
        while cycles >= 3:
            output += "    lpm\n"

        if cycles == 2:
            output += "    rjmp PC+1\n"

        elif cycles == 1:
            output += "    nop\n"

    else:
        output += "\n" + tabbify("; Cannot delay for this amount in this loop. Creating a new delay loop\n" +
                                 generate_wait(unique_label + "_Nest", cycles, first_register, "", 0))

    return output.strip()


def parse_notes():
    file = open("notes.csv")
    lines = file.readlines()

    output = []
    for line in lines:
        split = line.strip().split(",")
        output.append((split[0], float(split[1])))
    return output


def generate_note_waits(notes):
    output = ""
    for note in notes:
        note_name = note[0]
        note_half_period = note[1] / 2
        output += "\n{}Wait:\n".format(note_name)
        output += tabbify(generate_wait(note_name + "WaitLoop", time_to_cycles(note_half_period), 18, "", 0))
        output += "\nret\n"

    return output


def parse_midi(filename, notes):
    file = mido.MidiFile(filename)

    outnotes = []
    for message in file:
        if message.type == "note_on":
            pitch = message.note - 21
            off = message.velocity == 0
            outnotes.append((notes[pitch], message.time, off))

    return outnotes


def generate_note(note_name, note_period, time_before_note, note_duration):
    output = ""

    lowercase = "abcdefghijklmnopqrstuvwxyz"
    random_string = "".join(random.choices(lowercase, k=40))

    output += "\n" + generate_wait(note_name + "_PreWait_" + random_string, time_to_cycles(time_before_note), 21, "", 0) + "\n"

    note_code = tabbify("""out PORTB, r16
call {}Wait
out PORTB, r17
call {}Wait""".format(note_name, note_name)) + "\n"

    output += generate_wait(note_name + "_" + random_string, time_to_cycles(note_duration), 21, note_code,
                            time_to_cycles(note_period) + 2)

    return output


def generate_melody(note_sequence):
    output = ""
    for i, note in enumerate(note_sequence):
        # If the note is not off
        if not note[2]:
            related_notes = [note]
            # Check if any other notes start at the same time
            for n in note_sequence[i:]:
                if n[1] == 0:
                    related_notes.append(n)
                else:
                    break

            # Search for the time notes turns off
            for related_note in related_notes:
                for n in note_sequence[i:]:
                    if related_note[0][0] == n[0][0] and n[2]:
                        name = n[0][0]
                        period = n[0][1]
                        before = related_note[1]
                        duration = n[1]
                        output += "\n" + generate_note(name, period, before, duration)
                        break

    return output


if __name__ == "__main__":
    helptext = """midi-to-avrasm converts MIDI files into AVR Assembly
Connect a buzzer to pin 12 and GND if using ATmega328P

Usage: python miditoavrasm.py [options] <filename>
Options:
    -d --device     Device type. Defaults to ATmega328P
    -p --port       Port to output the waveform to. Defaults to B5
    -f --file       Output file. Defaults to song.asm
    -h --help       Prints this menu"""

    device = "atmega328P"
    file = "song.asm"

    opts, args = getopt.getopt(sys.argv[1:], "d:f:h", ["device=", "file=", "help"])

    if len(args) != 1:
        print(helptext)
        exit(1)

    outputfile = args[0]

    for opt, arg in opts:
        if opt in ["-d", "--device"]:
            device = arg
        elif opt in ["-f", "--file"]:
            file = arg
        elif opt in ["-h", "--help"]:
            print(helptext)
            exit(0)

    if not os.path.exists(outputfile):
        print("Error: File {} not found\n".format(outputfile))
        print(helptext)
        exit(1)

    output = """.device {}
.equ DDRB = 4
.equ PORTB = 5
ldi r16, $10
ldi r17, $0
out DDRB, r16
""".format(device)
    notes = parse_notes()

    midi = parse_midi(outputfile, notes)
    output += generate_melody(midi)

    output += generate_note_waits(notes)

    with open(file, "w") as file:
        file.write(output)
