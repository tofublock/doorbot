from telegram import Contact

class User(object):

	def __init__(self, contact, permissions=0):
		self.contact = contact
		self.message_id = 0
		self.permissions = permissions

class State(object):
	def __init__(self):
		self.locked = True
		self.accesslist = []
		self.users = []
