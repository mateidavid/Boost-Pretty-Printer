set pagination off
b done
r
p s
py v = gdb.parse_and_eval('s')
py boost_print.multi_index_1_42.idx[int(v.address)] = 1
p s
py boost_print.multi_index_1_42.idx[int(v.address)] = 2
p s
py boost_print.multi_index_1_42.idx[int(v.address)] = 3
p s
py boost_print.multi_index_1_42.idx[int(v.address)] = 4
p s
q
