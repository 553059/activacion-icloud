import re,sys,os
p = 'logs/activation_ticket_00008130-000135E60C06001C.xml'
if not os.path.exists(p):
    print('Ticket not found:', p)
    sys.exit(1)
s = open(p, 'r', encoding='utf-8').read()
# mask long digit sequences (leave last 4)
s_masked = re.sub(r"(\d{4})\d{4,}", lambda m: 'X'*(len(m.group(0))-4) + m.group(1), s)
print('PATH:', p)
print('\n--- preview (masked) ---\n')
print(s_masked[:1200])
