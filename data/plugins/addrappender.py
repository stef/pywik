def process(entry):
   if '?address=' in entry['path']:
      entry['bad']=['appaddr']
   return entry
