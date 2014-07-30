#include <boost/multi_index_container.hpp>
#include <boost/multi_index/ordered_index.hpp>
#include <boost/multi_index/hashed_index.hpp>
#include <boost/multi_index/sequenced_index.hpp>
#include <boost/multi_index/random_access_index.hpp>
#include <boost/multi_index/member.hpp>
#include <boost/multi_index/global_fun.hpp>
#include <tuple>

namespace bmi = boost::multi_index;

int negative(int x)
{
    return -x;
}

typedef boost::multi_index_container<
    int,
    bmi::indexed_by<
        bmi::sequenced<>,
        bmi::ordered_unique< bmi::identity< int > >,
        bmi::random_access<>,
        bmi::ordered_non_unique< bmi::global_fun< int, int, &negative > >,
        bmi::hashed_non_unique< bmi::identity< int > >
    >
> Int_Set;

Int_Set s;

void done() {}

int main()
{
    s.insert(s.end(), 0);
    s.insert(s.end(), 5);
    s.insert(s.end(), 17);
    s.insert(s.end(), 4);
    s.insert(s.end(), 14);
    s.insert(s.end(), 3);
    s.insert(s.end(), 9);
    done();  // break here
}
