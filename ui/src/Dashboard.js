import Dz from './Dz'
import ResponsiveAppBar from './ResponsiveAppBar'
import DashboardTable from './DashboardTable'
import {useEffect, useState} from 'react';
import { FETCH_PATH } from './environment'

function Dashboard() {
  const [isLoggedIn, setLogin] = useState(false);
  const [models, setModels] = useState([]);
  const [user, setUser] = useState(null)
  
  useEffect(() => {
    fetch(`${FETCH_PATH}/api/me`)
      .then(response => response.json())
      .then((data) => {
        if(data["redirect"] !== undefined){
          window.location.href = data.redirect;
        }  
        else{
          setLogin(true);
          setUser(data["user_data"]);
        }
      })
  },[]);

  useEffect(() => {
    fetch(`${FETCH_PATH}/api/models`)
      .then(response => response.json())
      .then((data) => {
       setModels(data.models);
      })
  },[]);

if(isLoggedIn){
  return (
    <div>
      <ResponsiveAppBar user={user}/>
      <h1>Dashboard</h1>
      <Dz />
      <DashboardTable models={models}/>
    </div>
    );
  }
}

export default Dashboard;
