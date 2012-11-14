#!/usr/bin/env python

import sys
import re

'''
A hacked together script I wrote in 30 mins for turning mips into irom.v
'''

preamble = '''
// Custom IROM with self-playing Pong

`include "mips_defines.v"

`define ADDR_WIDTH 9
`define INSTR_WIDTH 32
`define NUM_INSTR 512

module irom(clk, addr, dout);
    input clk;
    input [`ADDR_WIDTH-1:0] addr;
    output wire [`INSTR_WIDTH-1:0] dout;

    wire [`INSTR_WIDTH-1:0] memory [`NUM_INSTR-1:0];

    assign dout = memory[addr];

'''

if len(sys.argv) != 2:
  print 'usage: %s [filename]' % sys.argv[0]
  exit(1)

fin = open(sys.argv[1])
lines = fin.readlines()
fin.close()

def strip_after(lines, char):
  ret = []
  for line in lines:
    if line.find(char) >= 0:
      line = line[0:line.find(char)]
    ret.append(line)
  return ret

lines = strip_after(lines, '#')
lines = [line.strip() for line in lines if len(line.strip()) > 0]
lines = [line for line in lines if line[0] != '.']
lines = [re.sub(' +', ' ', line) for line in lines]
lines = [line for line in lines if line != 'syscall']

def flatten(l):
  return [ item for innerlist in l for item in innerlist ]

def tokenize(line):
  if line == 'nop':
    return ['nop']
  line = [line[:line.index(' ')], line[line.index(' '):]]
  line = [[line[0]], line[1].split(',')]
  line = flatten(line)
  line = [tok.strip() for tok in line]
  return line

def struct_ize(lines):
  ret = []
  tag = None
  for line in lines:
    if line[-1] == ':':
      tag = line[0:-1]
    else:
      ret.append({
        'tokens': tokenize(line),
        'text': line,
        'tag': tag
      })
      tag = None
  return ret

lines = struct_ize(lines)

def line_with_tag(lines, tag):
  for i in xrange(len(lines)):
    if lines[i]['tag'] == tag:
      return i
  return -1

def r2r(reg):
  if reg == '$sp':
    return '`SP'
  if reg == '$ra':
    return '`RA'
  if reg[0:2] == '$a':
    return '`A%d' % int(reg[2])
  if reg[0:2] == '$t':
    return '`T%d' % int(reg[2])
  if reg[0:2] == '$s':
    return '`S%d' % int(reg[2])
  if reg == '$zero':
    return '`ZERO'

def prot_neg(num):
  if num >= 0:
    return num
  return 65535 + num + 1

def asm(line, idx):
  toks = line['tokens']

  if toks[0] == 'nop':
    return '{`NOP}'

  # arithmetic

  if toks[0] == 'add':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `ADD}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'addu':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `ADDU}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'sub':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `SUB}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'slt':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `SLT}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'sltu':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `SLTU}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'or':
    return "{`SPECIAL, %s, %s, %s, 5'd0, `OR}" % (r2r(toks[2]), r2r(toks[3]), r2r(toks[1]))
  if toks[0] == 'sll':
    return "{`SPECIAL, `ZERO, %s, %s, 5'd%d, `SLL}" % (r2r(toks[2]), r2r(toks[1]), int(toks[3]))

  # arithmetic imm

  if toks[0] == 'addi':
    return "{`ADDI, %s, %s, 16'd%s}" % (r2r(toks[2]), r2r(toks[1]), prot_neg(int(toks[3])))
  if toks[0] == 'addiu':
    return "{`ADDIU, %s, %s, %s}" % (r2r(toks[2]), r2r(toks[1]), toks[3])
  if toks[0] == 'andi':
    return "{`ANDI, %s, %s, %s}" % (r2r(toks[2]), r2r(toks[1]), toks[3])
  if toks[0] == 'ori':
    return "{`ORI, %s, %s, 16'd%s}" % (r2r(toks[2]), r2r(toks[1]), toks[3])

  # load & store

  if toks[0] == 'lw':
    imm = toks[2][:toks[2].find('(')]
    reg = toks[2][toks[2].find('(')+1:-1]
    return "{`LW, %s, %s, 16'd%s}" % (r2r(reg), r2r(toks[1]), int(imm))
  if toks[0] == 'sw':
    imm = toks[2][:toks[2].find('(')]
    reg = toks[2][toks[2].find('(')+1:-1]
    return "{`SW, %s, %s, 16'd%s}" % (r2r(reg), r2r(toks[1]), int(imm))
  if toks[0] == 'li':
    return "{`ADDI, `ZERO, %s, 16'd%s}" % (r2r(toks[1]), prot_neg(int(toks[2])))
  if toks[0] == 'lui':
    return "{`LUI, `ZERO, %s, 16'd%s}" % (r2r(toks[1]), int(toks[2]))

  # jump

  if toks[0] == 'j':
    return "{`J, 26'd%d}" % line_with_tag(lines, toks[1])
  if toks[0] == 'jal':
    return "{`JAL, 26'd%d}" % line_with_tag(lines, toks[1])
  if toks[0] == 'jr':
    return "{`SPECIAL, %s, 15'd0, `JR}" % r2r(toks[1])

  # branch

  if toks[0] == 'bgtz':
    return "{`BGTZ, %s, 5'd0, 16'd%d}" % (r2r(toks[1]), prot_neg(line_with_tag(lines, toks[2]) - idx - 1))
  if toks[0] == 'bne':
    return "{`BNE, %s, %s, 16'd%d}" % (r2r(toks[1]), r2r(toks[2]), prot_neg(line_with_tag(lines, toks[3]) - idx - 1))
  if toks[0] == 'beq':
    return "{`BEQ, %s, %s, 16'd%d}" % (r2r(toks[1]), r2r(toks[2]), prot_neg(line_with_tag(lines, toks[3]) - idx - 1))
  if toks[0] == 'blez':
    return "{`BLEZ, %s, `ZERO, 16'd%d}" % (r2r(toks[1]), prot_neg(line_with_tag(lines, toks[2]) - idx - 1))
  if toks[0] == 'bltz':
    return "{`BLTZ_GEZ, %s, `BLTZ, 16'd%d}" % (r2r(toks[1]), prot_neg(line_with_tag(lines, toks[2]) - idx - 1))

i = 0
print preamble
for line in lines:
  if asm(line, i) == None:
    pass
    #print line['text']
  else:
    print '    assign memory[%3d] = %s;' % (i, asm(line, i))
  i += 1

print 'endmodule'

