# MIDI To Avr Assembly

This project is by no means complete and will never be but it does work

### Usage Instructions

---

1. Run the program like so:
```
Usage: python miditoavrasm.py [options] <filename>
Options:
    -d --device     Device type. Defaults to ATmega328P
    -f --file       Output file. Defaults to song.asm
    -h --help       Prints this menu
```

2. Upload the assembly file to the board

3. Connect the buzzer to PORTB 5 which corresponds to pin 12 on ATmega328P
