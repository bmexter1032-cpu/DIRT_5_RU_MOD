/* Linux x86-64 diagnostic harness. Maps original PE and executes actual language selector.
   No game process; mock ONLY locale provider, memcpy/strncmp IAT and command argument table.
   Build: gcc -O2 -Wall -o offline_test offline_test.c
   Run: ./offline_test original.exe locally_patched.exe */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <assert.h>
#include <signal.h>
#include <ucontext.h>
static void fault(int sig,siginfo_t*i,void*v){ucontext_t*c=v;fprintf(stderr,"signal %d addr %p RIP %llx RSP %llx RAX %llx RCX %llx RDX %llx\n",sig,i->si_addr,(long long)c->uc_mcontext.gregs[REG_RIP],(long long)c->uc_mcontext.gregs[REG_RSP],(long long)c->uc_mcontext.gregs[REG_RAX],(long long)c->uc_mcontext.gregs[REG_RCX],(long long)c->uc_mcontext.gregs[REG_RDX]);_Exit(1);}
#define MS __attribute__((ms_abi))
static uint32_t u32(const void*p){uint32_t x;memcpy(&x,p,4);return x;}
static uint16_t u16(const void*p){uint16_t x;memcpy(&x,p,2);return x;}
static uint64_t u64(const void*p){uint64_t x;memcpy(&x,p,8);return x;}
static void w64(void*p,uint64_t x){memcpy(p,&x,8);}
static uint32_t hash(const char*s){uint32_t h=0x811c9dc5;while(*s)h=(h^(unsigned char)*s++)*0x1000193;return h;}
static const char* locale;
static void * MS copy_mock(void*d,const void*s,size_t n){return memcpy(d,s,n);}
static int MS compare_mock(const char*a,const char*b,size_t n){return strncmp(a,b,n);}
static int MS locale_mock(int n,char*d){snprintf(d,n,"%s",locale);return 0;}
static void *map_pe(const char*path,uintptr_t addr){
    FILE*f=fopen(path,"rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char*b=malloc(n);assert(fread(b,1,n,f)==(size_t)n);fclose(f);
    unsigned char*p=b+u32(b+0x3c),*o=p+24,*s=o+u16(p+20);size_t size=u32(o+56);
    unsigned char*m=mmap((void*)addr,size,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);assert(m!=MAP_FAILED);
    memcpy(m,b,u32(o+60));for(int i=0;i<u16(p+6);i++,s+=40){uint32_t len=u32(s+16),raw=u32(s+20),rva=u32(s+12);assert(raw+len<=(unsigned long)n&&rva+len<=size);memcpy(m+rva,b+raw,len);}
    uint64_t delta=addr-u64(o+24);unsigned char*r=m+u32(o+112+5*8),*end=r+u32(o+116+5*8);
    while(r<end){uint32_t page=u32(r),len=u32(r+4);assert(len>=8&&r+len<=end);for(unsigned char*t=r+8;t<r+len;t+=2){uint16_t v=u16(t);if(v>>12==10){unsigned char*a=m+page+(v&4095);w64(a,u64(a)+delta);}else assert((v>>12)==0);}r+=len;}
    free(b);
    w64(m+0xc46748,(uintptr_t)copy_mock);
    w64(m+0xc467a8,(uintptr_t)compare_mock);
    unsigned char jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};w64(jump+2,(uintptr_t)locale_mock);memcpy(m+0x6c41d0,jump,sizeof jump);
    /* Test-only trampoline: actual call at 42c236 and return address 42c23b.
       It does not run the surrounding text loader, which is tested in the game. */
    unsigned char pre[]={0x48,0x83,0xec,0x28,0x90},post[]={0x48,0x83,0xc4,0x28,0xc3};
    memcpy(m+0x42c231,pre,sizeof pre);memcpy(m+0x42c23b,post,sizeof post);
    return m;
}
struct Arg{uint32_t key,pad;const char*value;void*next;};
typedef void (MS *select_fn)(char*);
static void run(unsigned char*m,const char*arg,int text,char*out){
    struct Arg a={hash("language"),0,arg,NULL};void**table=(void**)(m+0xe91680);memset(table,0,257*8);if(arg)table[a.key%257]=&a;
    select_fn f=(select_fn)(m+(text?0x42c231:0xf4bb0));memset(out,0,64);f(out);
}
int main(int argc,char**argv){assert(argc==3);struct sigaction sa={.sa_sigaction=fault,.sa_flags=SA_SIGINFO};sigaction(SIGSEGV,&sa,NULL);sigaction(SIGILL,&sa,NULL);const char*args[]={"eng","fre","spa","ger","ita","bra","sim","jap","kor","rus","RUS","r","ru","russ","rus-extra","", "invalid",NULL};const char*locs[]={"en-US","fr-FR","pt-BR","ru-RU","zh-CN"};
    unsigned char*original=map_pe(argv[1],0x140000000),*patched=map_pe(argv[2],0x240000000);int tests=0;
    for(int l=0;l<5;l++){locale=locs[l];for(int i=0;i<18;i++){for(int text=0;text<2;text++){char a[64],b[64];run(original,args[i],text,a);run(patched,args[i],text,b);const char*expect=(args[i]&&!strcmp(args[i],"rus"))?(text?"rus":"eng"):a;if(strcmp(b,expect)){fprintf(stderr,"FAIL: %s %s text=%d expected %s got %s\n",locale,args[i]?args[i]:"(missing)",text,expect,b);return 1;}tests++;}}}
    printf("PASS: %d actual selector calls compared against vanilla, relocated image; locale and IAT mocked.\n",tests);return 0;
}
