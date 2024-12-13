=====
event
=====

I wanted to throw a party and invite people to it.
Normally I'd just create a facebook event, but my friends no longer reliably use Facebook.
There are some competing tools, but all the ones I found were either

- aimed at business running corporate events
- kind of cringy
- expensive

So I built my own. This is a simple app that supports

- creating event invite pages
- credential-free RSVP to those events

My aim was for the RSVP process to be as painless as possible.


Instructions
============

.. code:: sh

   pip install -r requirements.txt
   python hash_pw.py > admin.passhash
   python initdb.py
   python website.py
