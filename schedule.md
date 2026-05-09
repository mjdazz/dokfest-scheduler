[1/40] https://www.dokfest-muenchen.de/films/enough-is-enough
[2/40] https://www.dokfest-muenchen.de/films/the-people-shall
[3/40] https://www.dokfest-muenchen.de/films/the-woman-who-poked-the-leopard
[4/40] https://www.dokfest-muenchen.de/films/the-magic-city-birmingham-selon-sun-ra
[5/40] https://www.dokfest-muenchen.de/films/becoming-kim
[6/40] https://www.dokfest-muenchen.de/films/politik-ist-persoenlich
^CTraceback (most recent call last):
  File [35m"/app/scrape_screenings.py"[0m, line [35m454[0m, in [35m<module>[0m
    [31mmain[0m[1;31m()[0m
    [31m~~~~[0m[1;31m^^[0m
  File [35m"/app/scrape_screenings.py"[0m, line [35m398[0m, in [35mmain[0m
    all_screenings.extend(parse([31mfetch[0m[1;31m(url)[0m))
                                [31m~~~~~[0m[1;31m^^^^^[0m
  File [35m"/app/scrape_screenings.py"[0m, line [35m91[0m, in [35mfetch[0m
    r = requests.get(url, headers=HEADERS, timeout=30)
  File [35m"/usr/local/lib/python3.13/site-packages/requests/api.py"[0m, line [35m73[0m, in [35mget[0m
    return request("get", url, params=params, **kwargs)
  File [35m"/usr/local/lib/python3.13/site-packages/requests/api.py"[0m, line [35m59[0m, in [35mrequest[0m
    return [31msession.request[0m[1;31m(method=method, url=url, **kwargs)[0m
           [31m~~~~~~~~~~~~~~~[0m[1;31m^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^[0m
  File [35m"/usr/local/lib/python3.13/site-packages/requests/sessions.py"[0m, line [35m592[0m, in [35mrequest[0m
    resp = self.send(prep, **send_kwargs)
  File [35m"/usr/local/lib/python3.13/site-packages/requests/sessions.py"[0m, line [35m706[0m, in [35msend[0m
    r = adapter.send(request, **kwargs)
  File [35m"/usr/local/lib/python3.13/site-packages/requests/adapters.py"[0m, line [35m645[0m, in [35msend[0m
    resp = conn.urlopen(
        method=request.method,
    ...<9 lines>...
        chunked=chunked,
    )
  File [35m"/usr/local/lib/python3.13/site-packages/urllib3/connectionpool.py"[0m, line [35m788[0m, in [35murlopen[0m
    response = self._make_request(
        conn,
    ...<10 lines>...
        **response_kw,
    )
  File [35m"/usr/local/lib/python3.13/site-packages/urllib3/connectionpool.py"[0m, line [35m534[0m, in [35m_make_request[0m
    response = conn.getresponse()
  File [35m"/usr/local/lib/python3.13/site-packages/urllib3/connection.py"[0m, line [35m571[0m, in [35mgetresponse[0m
    httplib_response = super().getresponse()
  File [35m"/usr/local/lib/python3.13/http/client.py"[0m, line [35m1450[0m, in [35mgetresponse[0m
    [31mresponse.begin[0m[1;31m()[0m
    [31m~~~~~~~~~~~~~~[0m[1;31m^^[0m
  File [35m"/usr/local/lib/python3.13/http/client.py"[0m, line [35m336[0m, in [35mbegin[0m
    version, status, reason = [31mself._read_status[0m[1;31m()[0m
                              [31m~~~~~~~~~~~~~~~~~[0m[1;31m^^[0m
  File [35m"/usr/local/lib/python3.13/http/client.py"[0m, line [35m297[0m, in [35m_read_status[0m
    line = str([31mself.fp.readline[0m[1;31m(_MAXLINE + 1)[0m, "iso-8859-1")
               [31m~~~~~~~~~~~~~~~~[0m[1;31m^^^^^^^^^^^^^^[0m
  File [35m"/usr/local/lib/python3.13/socket.py"[0m, line [35m719[0m, in [35mreadinto[0m
    return [31mself._sock.recv_into[0m[1;31m(b)[0m
           [31m~~~~~~~~~~~~~~~~~~~~[0m[1;31m^^^[0m
  File [35m"/usr/local/lib/python3.13/ssl.py"[0m, line [35m1304[0m, in [35mrecv_into[0m
    return [31mself.read[0m[1;31m(nbytes, buffer)[0m
           [31m~~~~~~~~~[0m[1;31m^^^^^^^^^^^^^^^^[0m
  File [35m"/usr/local/lib/python3.13/ssl.py"[0m, line [35m1138[0m, in [35mread[0m
    return [31mself._sslobj.read[0m[1;31m(len, buffer)[0m
           [31m~~~~~~~~~~~~~~~~~[0m[1;31m^^^^^^^^^^^^^[0m
[1;35mKeyboardInterrupt[0m
