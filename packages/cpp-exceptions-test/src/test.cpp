#include <exception>
using namespace std;

int g(int);

extern "C" int f(int x) {
    try {
        return g(x);
    }
    catch (int param) { 
        return param + 77;
    }
    catch (char param) { 
        return (int)param + 88;   
    }
    catch (exception & e){
        return 101;
    }
    catch (...) { 
        return 99;
    }
}

