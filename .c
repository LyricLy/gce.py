/* Code generated from .code */

#include <stdio.h>

#ifdef __STDC__
#include <limits.h>
/* LLONG_MAX came in after inttypes.h, limits.h is very old. */
#if _POSIX_VERSION >= 199506L || defined(LLONG_MAX)
#include <inttypes.h>
#endif
#endif

#if 0 /*1978 K&R*/
#elif defined(C) /*Okay*/
#elif defined(__SIZEOF_INT128__)
#define C unsigned __int128
#elif defined(_UINT128_T)
#define C __uint128_t
#elif defined(ULLONG_MAX) || defined(__LONG_LONG_MAX__)
#define C unsigned long long
#elif defined(UINTMAX_MAX)
#define C uintmax_t
#else
#define C unsigned int
#endif

#ifndef M
#define M(V) V
#endif

#ifdef __STDC__
enum { MaskTooSmall=1/(M(0x80)) };
#endif

#ifdef __STDC__
static C getch(C oldch);
#else
static C getch();
#endif

static C a;
int main(){
  setbuf(stdout, 0);

  a = getch(a);
  while(M(a)) {
	putchar(M(a));
	a = getch(a);
  }
  return 0;
}

#ifdef __STDC__
static C
getch(C oldch)
#else
static int getch(oldch) C oldch;
#endif
{
  int ch;
  ch = getchar();
#ifndef EOFCELL
  if (ch != EOF) return ch;
  return oldch;
#else
#if EOFCELL == EOF
  return ch;
#else
  if (ch != EOF) return ch;
  return EOFCELL;
#endif
#endif
}
