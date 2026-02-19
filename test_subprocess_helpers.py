import backend_modules as bm
print('RUN echo:', bm._run(['cmd','/c','echo','hello']))
print('STREAM echo:', bm._stream(['cmd','/c','echo','stream test']))
