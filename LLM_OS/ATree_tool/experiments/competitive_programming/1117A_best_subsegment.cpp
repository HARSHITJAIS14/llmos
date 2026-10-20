/**
 * Problem: Codeforces 1117A - Best Subsegment
 * Contest: Educational Codeforces Round 60 (Rated for Div. 2)
 *
 * Algorithm:
 * The maximum possible arithmetic mean for any subsegment is max(a).
 * Any subsegment with this mean must consist solely of elements equal to max(a).
 * Therefore, the problem reduces to finding the length of the longest contiguous
 * subsegment containing only the maximum element of the array.
 *
 * Complexity:
 * - Time: O(n)
 * - Space: O(n)
 */

#include <iostream>
#include <vector>
#include <algorithm>

using namespace std;

void solve() {
    int n;
    if (!(cin >> n)) return;
    
    vector<long long> a(n);
    long long max_val = -1;
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
        max_val = max(max_val, a[i]);
    }
    
    int max_len = 0;
    int current_len = 0;
    for (int i = 0; i < n; ++i) {
        if (a[i] == max_val) {
            current_len++;
            max_len = max(max_len, current_len);
        } else {
            current_len = 0;
        }
    }
    
    cout << max_len << "\n";
}

int main() {
    // Fast I/O
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    solve();
    
    return 0;
}
