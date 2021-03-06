import socket
import struct
from threading import Thread
import time

# Copyright (c) 2014, Florian Wesch <fw@dividuum.de>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
#     Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
# 
#     Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the
#     distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#^^ Applies to the following two functions, write_varint and size_varint
#https://github.com/dividuum/fastmc/blob/master/fastmc/proto.py#L110
def varint(value):
	result = bytearray()
	if value <= 127: # fast path
		result += bytearray((value,))
	else:
		shifted_value = True # dummy initialized
		while shifted_value:
			shifted_value = value >> 7
			result += bytearray(((value & 0x7f) | (0x80 if shifted_value else 0),))
			value = shifted_value
	return result
#https://github.com/dividuum/fastmc/blob/master/fastmc/proto.py#L119
def size_varint(value):
	size = 1
	while value & ~0x7f:
		size += 1
		value >>= 7
	return size

def decode_varint(value):
	msb = "1"
	num = 0
	value_length = []
	for rbyte in value:
		num += 1
		msb = '{0:08b}'.format(rbyte)[0:1]
		if msb == "0":
			value_length_bytes = value[0:num]
			for value_length_byte in value_length_bytes:
				msb = '{0:08b}'.format(value_length_byte)[0:1]
				if msb == "1":
					value_length.append('{0:08b}'.format(rbyte)[1:])
				else:
					value_length.append('{0:08b}'.format(rbyte))
			break
	value_length = value_length[::-1]
	value_length = ''.join(value_length)
	value_length = int(value_length, base = 2)
	return [value_length, num]

def decode_string(value):
	value_length, num = decode_varint(value)
	value = value[num:]
	return [value, value_length]

def writeString(toConvert):
	strByte = bytearray(toConvert, "utf-8")
	result = varint(len(strByte)) + strByte
	return result

def default_handler(self, packet_id, data):
		pass

class Connect:
	def __init__(self, ip, port, handler = None, debug = False, ):
		self.ip = ip
		self.port = port
		self.debug = debug
		self.s = socket.socket()
		self.thread_id = 0
		if handler != None:
			self.handler = handler
		else:
			self.handler = default_handler
	def sendPacket(self, id, data = None):
		if str(type(id)) == "<class 'int'>":
			id = bytearray((id,))
		if (data != None and str(type(data)) == "<class 'bytearray'>") or (data == None):
			if data != None:
				if self.debug:
					print("Sent: " + ''.join(r'\x' + hex(letter)[2:] for letter in varint(len(data) + len(id))))
				self.s.send(bytearray((len(data)+len(id),)))
			else:
				if self.debug:
					print("Sent: " + ''.join(r'\x' + hex(letter)[2:] for letter in bytes((1,))))
				self.s.send(bytes((1,)))
			if self.debug:
				print("Sent: " + ''.join(r'\x' + hex(letter)[2:] for letter in bytearray(id)))
			self.s.send(bytearray(id))
			if data != None:
				if self.debug:
					print("Sent: " + ''.join(r'\x' + hex(letter)[2:] for letter in data))
				self.s.send(data)
		else:
			raise TypeError
	def status(self):
		self.connect()
		packet = bytearray()
		packet_id = b'\x00'
		packet += varint(210)
		packet += writeString(self.ip)
		packet += struct.pack("!H", self.port)
		packet += varint(1)
		self.sendPacket(packet_id, packet)
		self.sendPacket(b'\x00')
		self.status_mode = True
		self.status_response = ""
		time.sleep(1)
		self.status_mode = False
		self.disconect()
		return self.status_response
	def connect(self):
		self.s.connect((self.ip,self.port))
		self.thread = Thread(target = self.receive)
		self.thread.start()
	def disconect(self):
		self.thread_id += 1
	def receive(self):
		priv_id = self.thread_id
		while self.thread_id == priv_id:
			try:
				response = self.s.recv(4096)
				if response:
					response_length, num = decode_varint(response)
					response_id = response[num:num+1]
					data, data_length = decode_string(response[num+1:])
					if self.debug:
						response_id_debug = str(response_id)
						response_id_debug = "0x" + str(response_id_debug)[4:len(str(response_id_debug))-1].upper()
						print("(" + str(response_length) + " vs. " + str(1 + len(response[num:])) + ") Packet ID " + response_id_debug)
						print("Data: " + str(data))
					if self.status_mode == True:
						if response_id == 0x00:
							self.status_response = data
					self.handler(self, response_id, data)
			except BlockingIOError:
				pass
		self.s.disconect()
