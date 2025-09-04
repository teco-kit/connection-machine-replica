def test(x,y):
    res = y * 16
    if y % 2 == 0:
        res = res + x
    else:
        res = res + (15 - x)
    return res
        
        
print(test(0,2))