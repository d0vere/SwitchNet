#!/usr/bin/env python3
DEFAULT={
"LS_UP":"W","LS_DOWN":"S","LS_LEFT":"A","LS_RIGHT":"D","ZL":"Q","ZR":"O",
"DPAD_UP":"UP","DPAD_DOWN":"DOWN","DPAD_LEFT":"LEFT","DPAD_RIGHT":"RIGHT",
"L":"E","R":"U","X":"I","Y":"J","B":"K","A":"L","L3":"X","R3":"M",
"PLUS":"Y","MINUS":"T","CAPTURE":"G","HOME":"B",
}
expected={
"W":"LS_UP","S":"LS_DOWN","A":"LS_LEFT","D":"LS_RIGHT",
"Q":"ZL","O":"ZR","E":"L","U":"R","I":"X","J":"Y","K":"B","L":"A",
"X":"L3","M":"R3","Y":"PLUS","T":"MINUS","G":"CAPTURE","B":"HOME",
}
for key,action in expected.items(): assert DEFAULT[action]==key
assert DEFAULT["DPAD_UP"]=="UP" and DEFAULT["DPAD_DOWN"]=="DOWN"
print("OK: requested default keyboard mapping")
