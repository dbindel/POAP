#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char** argv)
{
    double x = atof(argv[1]);
    double fx = (x-0.123)*(x-0.123);
    sleep(5);
    printf("%g\n", fx);
    return 0;
}
