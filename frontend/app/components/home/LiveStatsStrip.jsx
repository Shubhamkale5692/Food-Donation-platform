import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CountUp from 'react-countup';

const LiveStatsStrip = () => {
  const [stats, setStats] = useState({
    mealsDelivered: 0,
    activeDonors: 0,
    partnerNGOs: 0,
    volunteers: 0,
  });

  // Function to fetch live stats from the backend
  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/v1/stats/dashboard-summary');
      if (response.data && response.data.success) {
        setStats({
          mealsDelivered: response.data.data.mealsDelivered || 0,
          activeDonors: response.data.data.activeDonors || 0,
          partnerNGOs: response.data.data.partnerNGOs || 0,
          volunteers: response.data.data.volunteers || 0,
        });
      }
    } catch (error) {
      console.error('Failed to fetch live statistics:', error);
    }
  };

  useEffect(() => {
    // Initial fetch on component mount
    fetchStats();

    // Real-time Sync: Polling every 10 seconds for live updates
    const intervalId = setInterval(fetchStats, 10000);

    // Cleanup interval on component unmount
    return () => clearInterval(intervalId);
  }, []);

  return (
    <section className="home-stats-strip py-5 text-white fade-in-up delay-4 bg-success">
      <div className="container py-3">
        <div className="row text-center g-4">
          
          <div className="col-6 col-md-3 stat-item">
            <h2 className="display-4 fw-bold mb-2">
              <CountUp start={0} end={stats.mealsDelivered} duration={2.5} separator="," />
            </h2>
            <div className="stat-divider mx-auto mb-3"></div>
            <p className="mb-0 text-white-50 fw-semibold text-uppercase tracking-wide">
              Meals Delivered
            </p>
          </div>
          
          <div className="col-6 col-md-3 stat-item">
            <h2 className="display-4 fw-bold mb-2">
              <CountUp start={0} end={stats.activeDonors} duration={2.5} separator="," />
            </h2>
            <div className="stat-divider mx-auto mb-3"></div>
            <p className="mb-0 text-white-50 fw-semibold text-uppercase tracking-wide">
              Active Donors
            </p>
          </div>
          
          <div className="col-6 col-md-3 stat-item">
            <h2 className="display-4 fw-bold mb-2">
              <CountUp start={0} end={stats.partnerNGOs} duration={2.5} separator="," />
            </h2>
            <div className="stat-divider mx-auto mb-3"></div>
            <p className="mb-0 text-white-50 fw-semibold text-uppercase tracking-wide">
              Partner NGOs
            </p>
          </div>
          
          <div className="col-6 col-md-3 stat-item">
            <h2 className="display-4 fw-bold mb-2">
              <CountUp start={0} end={stats.volunteers} duration={2.5} separator="," />
            </h2>
            <div className="stat-divider mx-auto mb-3"></div>
            <p className="mb-0 text-white-50 fw-semibold text-uppercase tracking-wide">
              Volunteers
            </p>
          </div>
          
        </div>
      </div>
    </section>
  );
};

export default LiveStatsStrip;
