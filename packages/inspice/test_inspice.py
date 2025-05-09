from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["inspice"])
def test_mytestname(selenium):
    from InSpice.Spice.NgSpice.Shared import NgSpiceShared
    ngspice = NgSpiceShared()
    circuit = '''
    .title Voltage Multiplier

    .SUBCKT 1N4148 1 2
    *
    R1 1 2 5.827E+9
    D1 1 2 1N4148
    *
    .MODEL 1N4148 D
    + IS = 4.352E-9
    + N = 1.906
    + BV = 110
    + IBV = 0.0001
    + RS = 0.6458
    + CJO = 7.048E-13
    + VJ = 0.869
    + M = 0.03
    + FC = 0.5
    + TT = 3.48E-9
    .ENDS

    Vinput in 0 DC 0V AC 1V SIN(0V 10V 50Hz 0s 0Hz)
    C0 in 1 1mF
    X0 1 0 1N4148
    C1 0 2 1mF
    X1 2 1 1N4148
    C2 1 3 1mF
    X2 3 2 1N4148
    C3 2 4 1mF
    X3 4 3 1N4148
    C4 3 5 1mF
    X4 5 4 1N4148
    R1 5 6 1MegOhm
    .options TEMP = 25°C
    .options TNOM = 25°C
    .options filetype = binary
    .options NOINIT
    .ic
    .tran 0.0001s 0.4s 0s
    .end
    '''
    ngspice.load_circuit(circuit)
    ngspice.run()
    plot = ngspice.plot(simulation=None, plot_name=ngspice.last_plot)
    assert "V(6)" in plot